from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import sys
import threading

# Asegurar que reconozca los scripts de lógica
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from fastapi.responses import JSONResponse
from scripts.db_manager import create_connection
from scripts.poisson_model import calculate_team_strengths, predict_match
from scripts.ingestion import sync_fixtures, download_and_import_massive, cleanup_stale_scheduled_matches
from scripts.evaluate_results import evaluate_recent_matches
from scripts.learning_module import train_adjustment_factors
from scripts.config import load_config, save_config
from datetime import datetime

app = FastAPI(title="Sports AI Service")

# Configuración de estáticos y plantillas
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# --- LIMPIEZA DE LOGS ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(BASE_DIR, "web/static/favicon.ico"))

@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools():
    return {"status": "ok"}

# --- ESTADO GLOBAL ---
config_data = load_config()
system_status = {
    "last_sync": config_data.get("last_sync_time_str", "No sincronizado"),
    "is_syncing": False,
    "last_accuracy": config_data.get("last_accuracy", 0),
    "season_active": config_data.get("season_active", True),
    "sync_message": config_data.get("sync_message", "")
}

def run_full_sync():
    """
    Orquestación completa de actualización y retroalimentación.
    Se ejecuta SOLO cuando el usuario presiona el botón Sincronizar en la UI.
    NO se llama automáticamente al arrancar el servidor.
    """
    global system_status
    system_status["is_syncing"] = True
    system_status["sync_message"] = "Sincronización en progreso..."
    print("\n[SYNC] Iniciando sincronización integral (disparada manualmente)...")

    try:
        # 0. Limpiar partidos 'scheduled' cuya fecha ya pasó
        _conn = create_connection()
        if _conn:
            cleanup_stale_scheduled_matches(_conn)
            _conn.close()

        # 1. Actualizar resultados de partidos finalizados (incremental desde la BD)
        download_and_import_massive()

        # 2. Sincronizar fixtures futuros (con fallback a proxy automático)
        fixture_result = sync_fixtures()
        fixtures_found = fixture_result.get("fixtures_found", 0)
        fixture_status = fixture_result.get("status", "error")
        fixture_msg = fixture_result.get("message", "")

        # Determinar si la temporada está activa según los fixtures encontrados
        season_active = (fixture_status == "ok" and fixtures_found > 0)
        system_status["season_active"] = season_active
        system_status["sync_message"] = fixture_msg

        # 3. Evaluar predicciones pasadas (marcar aciertos/fallos)
        eval_stats = evaluate_recent_matches(days=14, silent=True)
        if eval_stats and eval_stats["total"] > 0:
            system_status["last_accuracy"] = round((eval_stats["hits"] / eval_stats["total"]) * 100, 1)

        # 4. Ajustar factores de la neurona (aprendizaje)
        train_adjustment_factors(silent=True)

        system_status["last_sync"] = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Guardar estado en config de forma persistente
        config_data = load_config()
        config_data["last_sync_date"] = datetime.now().strftime("%Y-%m-%d")
        config_data["last_sync_time_str"] = system_status["last_sync"]
        config_data["last_accuracy"] = system_status["last_accuracy"]
        config_data["season_active"] = season_active
        config_data["sync_message"] = fixture_msg
        save_config(config_data)

        print(f"[SYNC] Finalizado. Fixtures: {fixtures_found} | Temporada activa: {season_active} | Precisión: {system_status['last_accuracy']}%")

    except Exception as e:
        msg = f"Error durante la sincronización: {e}"
        system_status["sync_message"] = msg
        print(f"[SYNC] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        system_status["is_syncing"] = False
        print("[SYNC] Proceso terminado.")

# --- API DE SINCRONIZACIÓN MANUAL ---
@app.post("/api/sync")
async def api_sync_trigger():
    """Dispara la sincronización completa en un hilo aparte. Llamado por el botón en la UI."""
    if system_status["is_syncing"]:
        return JSONResponse(
            status_code=409,
            content={"status": "busy", "message": "Ya hay una sincronización en curso. Por favor espera."}
        )
    thread = threading.Thread(target=run_full_sync, daemon=True)
    thread.start()
    return JSONResponse(
        status_code=202,
        content={"status": "started", "message": "Sincronización iniciada. Monitorea el estado en /api/sync/status"}
    )

@app.get("/api/sync/status")
async def api_sync_status():
    """Retorna el estado actual de la sincronización. Usado por la UI para polling."""
    return JSONResponse(content={
        "is_syncing": system_status["is_syncing"],
        "last_sync": system_status["last_sync"],
        "last_accuracy": system_status["last_accuracy"],
        "season_active": system_status["season_active"],
        "sync_message": system_status["sync_message"]
    })

# Mantener compatibilidad con la URL antigua (GET /sync)
@app.get("/sync")
async def sync_data_legacy():
    """Ruta legacy. Usar POST /api/sync desde la UI."""
    if system_status["is_syncing"]:
        return {"status": "busy", "message": "Sincronización en curso"}
    thread = threading.Thread(target=run_full_sync, daemon=True)
    thread.start()
    return {"status": "started"}

# --- SERVICIOS ---
def get_db_stats():
    conn = create_connection()
    if not conn: return {"matches": 0, "teams": 0, "leagues": []}
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    # Globales (Filtrados por las 5 grandes ligas)
    cursor.execute("""
        SELECT COUNT(*) as total 
        FROM matches m
        JOIN leagues l ON m.league_id = l.id
        WHERE l.name IN ('Premier League', 'La Liga', 'Bundesliga', 'Ligue 1', 'Serie A')
    """)
    total_matches = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM teams")
    total_teams = cursor.fetchone()['total']
    
    # Desglose por liga (Filtrado por las 5 grandes)
    cursor.execute("""
        SELECT l.name, COUNT(m.id) as match_count, 
               ROUND(AVG(m.home_goals + m.away_goals), 2) as avg_goals
        FROM leagues l
        LEFT JOIN matches m ON l.id = m.league_id
        WHERE l.name IN ('Premier League', 'La Liga', 'Bundesliga', 'Ligue 1', 'Serie A')
        GROUP BY l.id
        ORDER BY match_count DESC
    """)
    leagues_data = cursor.fetchall()
    
    # Calcular el máximo de partidos para las barras de progreso
    max_matches = max([l['match_count'] for l in leagues_data]) if leagues_data else 100
    
    conn.close()
    return {
        "matches": total_matches, 
        "teams": total_teams, 
        "leagues": leagues_data,
        "max_matches": max_matches
    }

# --- RUTAS PRINCIPALES ---
@app.get("/")
async def index(request: Request):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    # Modificar la consulta para evitar duplicados y filtrar por las 5 grandes ligas
    query = """
        SELECT DISTINCT m.date, l.name as league, t1.name as home, t2.name as away, 
               m.home_goals, m.away_goals, 
               m.ht_home_goals, m.ht_away_goals,
               m.home_shots, m.away_shots, 
               m.home_shots_on_target, m.away_shots_on_target, 
               m.home_corners, m.away_corners,
               m.home_fouls, m.away_fouls,
               m.home_yellow_cards, m.away_yellow_cards,
               m.home_red_cards, m.away_red_cards,
               m.status,
               o.home_win_odds, o.draw_odds, o.away_win_odds,
               o.handicap_line, o.home_handicap_odds, o.away_handicap_odds
        FROM matches m
        JOIN leagues l ON m.league_id = l.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        LEFT JOIN odds o ON m.id = o.match_id
        WHERE l.name IN ('Premier League', 'La Liga', 'Bundesliga', 'Ligue 1', 'Serie A')
        ORDER BY (DATE(m.date) = CURRENT_DATE()) DESC, (m.status = 'finished') DESC, m.date DESC 
        LIMIT 20
    """
    cursor.execute(query)
    matches = cursor.fetchall()
    conn.close()
    stats = get_db_stats()
    return templates.TemplateResponse(request=request, name="index.html", context={
        "matches": matches, 
        "stats": stats,
        "system": system_status
    })

@app.get("/pronosticos")
async def pronosticos(request: Request):
    # NOTA: La sincronización de fixtures ya NO se dispara automáticamente al visitar esta página.
    # El usuario debe usar el botón "Sincronizar" en el sidebar para actualizar los datos.
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    strengths = calculate_team_strengths()
    grouped_predictions = {}
    all_predictions = []
    top_picks = []
    
    if strengths:
        # Traer más partidos para cubrir las 5 ligas
        cursor.execute("""
            SELECT m.id, m.date, t1.name as home, t2.name as away, m.home_team_id, m.away_team_id, l.name as league
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            JOIN leagues l ON m.league_id = l.id
            WHERE m.status = 'scheduled' AND m.date > NOW()
            ORDER BY m.date ASC LIMIT 100
        """)
        future_matches = cursor.fetchall()
        
        for m in future_matches:
            try:
                p = predict_match(m['home_team_id'], m['away_team_id'], strengths)
                if p:
                    date_obj = m['date']
                    if isinstance(date_obj, str):
                        date_str = date_obj
                    elif date_obj:
                        date_str = date_obj.strftime('%d/%m/%Y %H:%M')
                    else:
                        date_str = "Fecha por definir"

                    prediction_data = {
                        "id": m['id'],
                        "date": date_str,
                        "league": m['league'],
                        "home": m['home'], "away": m['away'],
                        "home_win": p['home_win'], "draw": p['draw'], "away_win": p['away_win'],
                        "over_2_5": p['over_2_5'], "btts": p['btts'],
                        "exp_corners": p['exp_corners'], "exp_cards": p['exp_cards'],
                        "confidence": p['advice']['conf'] if p['advice'] else 0,
                        "prediction": p['advice']['label'] if p['advice'] else "N/A",
                        "handicap": p['expected_score'],
                        "ah_suggestion": p['ah_suggestion'],
                        "advice": p['advice']
                    }
                    
                    # Añadir a top picks si la confianza es alta
                    if prediction_data['confidence'] > 70:
                        top_picks.append(prediction_data)

                    league = m['league']
                    if league not in grouped_predictions:
                        grouped_predictions[league] = []
                    grouped_predictions[league].append(prediction_data)
                    all_predictions.append(prediction_data)
            except Exception as e:
                print(f"Error procesando partido {m.get('id')}: {e}")
                continue
    
    # Ordenar Top Picks por confianza descendente
    top_picks = sorted(top_picks, key=lambda x: x['confidence'], reverse=True)
    
    conn.close()
    return templates.TemplateResponse(request=request, name="pronosticos.html", context={
        "grouped_matches": grouped_predictions,
        "all_predictions": all_predictions,
        "top_picks": top_picks,
        "system": system_status
    })

@app.get("/ligas")
async def ligas(request: Request):
    stats = get_db_stats()
    return templates.TemplateResponse(request=request, name="ligas.html", context={"stats": stats})

@app.get("/equipos")
async def equipos(request: Request, search: str = "", liga: str = ""):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    query = "SELECT t.*, l.name as league_name FROM teams t JOIN leagues l ON t.league_id = l.id WHERE 1=1"
    params = []
    if search:
        query += " AND t.name LIKE %s"
        params.append(f"%{search}%")
    if liga:
        query += " AND l.name = %s"
        params.append(liga)
    query += " LIMIT 100"
    cursor.execute(query, params)
    teams = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="equipos.html", context={"teams": teams, "search": search, "liga": liga})

@app.get("/modelos")
async def modelos(request: Request):
    return templates.TemplateResponse(request=request, name="modelos.html", context={})

@app.get("/historico")
async def historico(request: Request):
    return templates.TemplateResponse(request=request, name="historico.html", context={})

@app.get("/review")
async def review(request: Request):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    # Obtener estadísticas de la tabla de predicciones
    cursor.execute("""
        SELECT market, 
               COUNT(*) as total, 
               SUM(CASE WHEN is_hit = 1 THEN 1 ELSE 0 END) as hits
        FROM predictions
        GROUP BY market
    """)
    stats_raw = cursor.fetchall()
    
    # Obtener los 10 mejores equipos por aciertos
    cursor.execute("""
        SELECT t.name, COUNT(*) as total, SUM(is_hit) as hits, 
               ROUND(SUM(is_hit)/COUNT(*)*100, 1) as accuracy
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t ON (m.home_team_id = t.id OR m.away_team_id = t.id)
        WHERE p.is_hit IS NOT NULL
        GROUP BY t.id
        ORDER BY hits DESC, accuracy DESC
        LIMIT 10
    """)
    top_teams = cursor.fetchall()

    # Obtener el mercado más predecible
    cursor.execute("""
        SELECT market, COUNT(*) as total, SUM(is_hit) as hits,
               ROUND(SUM(is_hit)/COUNT(*)*100, 1) as accuracy
        FROM predictions
        WHERE is_hit IS NOT NULL
        GROUP BY market
        ORDER BY accuracy DESC
    """)
    market_stats = cursor.fetchall()

    # Obtener los últimos 50 resultados evaluados
    cursor.execute("""
        SELECT p.*, m.date, t1.name as home, t2.name as away, m.home_goals, m.away_goals
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        ORDER BY m.date DESC LIMIT 50
    """)
    recent_reviews = cursor.fetchall()
    conn.close()
    
    total_evals = sum([m['total'] for m in market_stats])
    total_hits = sum([m['hits'] for m in market_stats])
    global_accuracy = (total_hits / total_evals * 100) if total_evals > 0 else 0
    
    return templates.TemplateResponse(request=request, name="review.html", context={
        "stats": market_stats,
        "top_teams": top_teams,
        "total_evals": total_evals,
        "global_accuracy": round(global_accuracy, 1),
        "recent_reviews": recent_reviews
    })

if __name__ == "__main__":
    uvicorn.run("web.main:app", host="0.0.0.0", port=8080, reload=True)
