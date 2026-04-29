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

from scripts.db_manager import create_connection
from scripts.poisson_model import calculate_team_strengths, predict_match
from scripts.ingestion import sync_fixtures, download_and_import_massive

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

# --- RUTAS DE SINCRONIZACIÓN ---
@app.get("/sync")
async def sync_data(request: Request):
    thread = threading.Thread(target=download_and_import_massive)
    thread.start()
    return {"status": "Sync started in background"}

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
               o.home_win_odds, o.draw_odds, o.away_win_odds,
               o.handicap_line, o.home_handicap_odds, o.away_handicap_odds
        FROM matches m
        JOIN leagues l ON m.league_id = l.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        LEFT JOIN odds o ON m.id = o.match_id
        WHERE l.name IN ('Premier League', 'La Liga', 'Bundesliga', 'Ligue 1', 'Serie A')
        ORDER BY m.date DESC LIMIT 20
    """
    cursor.execute(query)
    matches = cursor.fetchall()
    conn.close()
    stats = get_db_stats()
    return templates.TemplateResponse(request=request, name="index.html", context={"matches": matches, "stats": stats})

@app.get("/pronosticos")
async def pronosticos(request: Request):
    # Sincronización rápida de fixtures al entrar (opcional)
    thread = threading.Thread(target=sync_fixtures)
    thread.start()
    
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    strengths = calculate_team_strengths()
    grouped_predictions = {}
    top_picks = []
    
    if strengths:
        # Traer más partidos para cubrir las 5 ligas
        cursor.execute("""
            SELECT m.id, m.date, t1.name as home, t2.name as away, m.home_team_id, m.away_team_id, l.name as league
            FROM matches m
            JOIN teams t1 ON m.home_team_id = t1.id
            JOIN teams t2 ON m.away_team_id = t2.id
            JOIN leagues l ON m.league_id = l.id
            WHERE m.status = 'scheduled' 
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
            except Exception as e:
                print(f"Error procesando partido {m.get('id')}: {e}")
                continue
    
    # Ordenar Top Picks por confianza descendente
    top_picks = sorted(top_picks, key=lambda x: x['confidence'], reverse=True)
    
    conn.close()
    return templates.TemplateResponse(request=request, name="pronosticos.html", context={
        "grouped_matches": grouped_predictions,
        "top_picks": top_picks
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

if __name__ == "__main__":
    uvicorn.run("web.main:app", host="0.0.0.0", port=8080, reload=True)
