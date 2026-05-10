import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# Asegurar que reconozca los scripts de lógica
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection
from scripts.poisson_model import calculate_team_strengths, predict_match

def check_hit(market, label, home_goals, away_goals, home_corners=None, away_corners=None):
    if home_goals is None or away_goals is None:
        return None
    
    if market == "1X2":
        if "Local" in label and home_goals > away_goals: return True
        if "Visitante" in label and away_goals > home_goals: return True
        return False
    
    if market == "Goles":
        total = home_goals + away_goals
        if "Over 2.5" in label and total > 2.5: return True
        if "Under 2.5" in label and total < 2.5: return True
        return False
    
    if market == "BTTS":
        btts = home_goals > 0 and away_goals > 0
        if "SÍ" in label and btts: return True
        if "NO" in label and not btts: return True
        return False
    
    if market == "Córners" and home_corners is not None and away_corners is not None:
        total_corners = home_corners + away_corners
        if "Más de 9.5" in label and total_corners > 9.5: return True
        return False
        
    return False

def evaluate_recent_matches(days=7, silent=False):
    conn = create_connection()
    if not conn: return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    if not silent: print(f"Calculando fortalezas de equipos...")
    strengths = calculate_team_strengths()
    
    # Buscar partidos finalizados recientemente
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    if not silent: print(f"Buscando partidos desde {start_date}...")
    
    query = """
        SELECT m.id, m.date, l.name as league, t1.name as home, t2.name as away, 
               m.home_team_id, m.away_team_id, m.home_goals, m.away_goals,
               m.home_corners, m.away_corners
        FROM matches m
        JOIN leagues l ON m.league_id = l.id
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.status = 'finished' AND m.date >= %s
    """
    cursor.execute(query, (start_date,))
    matches = cursor.fetchall()
    
    stats = {"hits": 0, "misses": 0, "total": 0, "by_market": {}}
    
    if not silent: print(f"Evaluando {len(matches)} partidos...")
    
    for m in matches:
        p = predict_match(m['home_team_id'], m['away_team_id'], strengths)
        if not p or not p['advice'] or p['advice']['conf'] == 0:
            continue
            
        advice = p['advice']
        market = advice['market']
        label = advice['label']
        conf = advice['conf']
        
        is_hit = check_hit(market, label, m['home_goals'], m['away_goals'], m['home_corners'], m['away_corners'])
        
        # Guardar predicción en la DB
        try:
            cursor.execute("""
                INSERT INTO predictions (match_id, market, prediction_label, confidence, is_hit)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE is_hit = VALUES(is_hit)
            """, (m['id'], market, label, conf, is_hit))
        except Exception as e:
            pass
            
        # Estadísticas locales
        stats["total"] += 1
        if is_hit: stats["hits"] += 1
        else: stats["misses"] += 1
        
        if market not in stats["by_market"]:
            stats["by_market"][market] = {"hits": 0, "misses": 0}
        
        if is_hit: stats["by_market"][market]["hits"] += 1
        else: stats["by_market"][market]["misses"] += 1
        
        # Print individual result
        res_icon = "[OK]" if is_hit else "[X]"
        if not silent: print(f"{res_icon} [{market}] {m['home']} {m['home_goals']}-{m['away_goals']} {m['away']} -> Pred: {label} ({conf}%)")

    conn.commit()
    conn.close()
    
    if not silent:
        print("\n" + "="*30)
        print("RESUMEN DE DESEMPEÑO")
        print("="*30)
        if stats["total"] > 0:
            accuracy = (stats["hits"] / stats["total"]) * 100
            print(f"Total Evaluados: {stats['total']}")
            print(f"Aciertos: {stats['hits']}")
            print(f"Fallos: {stats['misses']}")
            print(f"Precisión Global: {accuracy:.1f}%")
            
            print("\nDesglose por Mercado:")
            for mkt, s in stats["by_market"].items():
                mkt_acc = (s['hits'] / (s['hits'] + s['misses'])) * 100
                print(f"- {mkt}: {mkt_acc:.1f}% ({s['hits']}/{s['hits']+s['misses']})")
        else:
            print("No hay suficientes partidos con predicciones para evaluar.")
        print("="*30)
    
    return stats

if __name__ == "__main__":
    evaluate_recent_matches()
