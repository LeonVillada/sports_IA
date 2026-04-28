import mysql.connector
from scripts.db_manager import create_connection
import datetime

def manual_sync():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.execute("USE sports_ai_db")

    # Mapeo de ligas
    league_map = {
        "Premier League": 3,
        "La Liga": 383,
        "Serie A": 1523,
        "Bundesliga": 1903,
        "Ligue 1": 2209
    }

    # Resultados a inyectar con estadísticas avanzadas
    results = [
        # Premier League
        ("2026-04-25", "Premier League", "Arsenal", "Newcastle", 1, 0, 11, 13, 4, 3, 7, 2),
        ("2026-04-25", "Premier League", "Fulham", "Aston Villa", 1, 0, 12, 9, 5, 2, 4, 6),
        ("2026-04-25", "Premier League", "Liverpool", "Crystal Palace", 3, 1, 18, 7, 9, 3, 8, 2),
        
        # La Liga
        ("2026-04-24", "La Liga", "Real Betis", "Real Madrid", 1, 1, 19, 12, 4, 8, 7, 6),
        ("2026-04-25", "La Liga", "Getafe", "Barcelona", 0, 2, 7, 15, 2, 7, 3, 5),
        ("2026-04-25", "La Liga", "Atletico Madrid", "Athletic Club", 3, 2, 14, 11, 6, 5, 5, 4),
        
        # Bundesliga
        ("2026-04-25", "Bundesliga", "Mainz", "Bayern Munich", 3, 4, 11, 21, 6, 8, 4, 4),
        ("2026-04-26", "Bundesliga", "Dortmund", "Freiburg", 4, 0, 16, 5, 7, 1, 6, 2),
        
        # Serie A
        ("2026-04-26", "Serie A", "Milan", "Juventus", 0, 0, 8, 10, 1, 5, 1, 3),
        ("2026-04-26", "Serie A", "Torino", "Inter", 2, 2, 10, 14, 4, 6, 4, 7),
        
        # Ligue 1
        ("2026-04-25", "Ligue 1", "Angers", "Paris SG", 0, 3, 6, 17, 1, 10, 5, 4),
        ("2026-04-26", "Ligue 1", "Marseille", "Nice", 1, 1, 12, 11, 5, 4, 6, 5),
    ]

    for date, league_name, home, away, hg, ag, hs, aws, hst, ast, hc, ac in results:
        try:
            league_id = league_map.get(league_name)
            
            # Obtener equipos
            cursor.execute("SELECT id FROM teams WHERE name = %s", (home,))
            res = cursor.fetchone()
            if not res: continue
            home_id = res[0]
            
            cursor.execute("SELECT id FROM teams WHERE name = %s", (away,))
            res = cursor.fetchone()
            if not res: continue
            away_id = res[0]

            # Insertar o actualizar partido
            sql = """
                INSERT INTO matches (
                    date, league_id, home_team_id, away_team_id, home_goals, away_goals, 
                    home_shots, away_shots, home_shots_on_target, away_shots_on_target, 
                    home_corners, away_corners, status, season
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    home_goals=VALUES(home_goals), away_goals=VALUES(away_goals),
                    home_shots=VALUES(home_shots), away_shots=VALUES(away_shots),
                    home_shots_on_target=VALUES(home_shots_on_target), away_shots_on_target=VALUES(away_shots_on_target),
                    home_corners=VALUES(home_corners), away_corners=VALUES(away_corners)
            """
            cursor.execute(sql, (date, league_id, home_id, away_id, hg, ag, hs, aws, hst, ast, hc, ac, 'finished', '2526'))
            
        except Exception as e:
            print(f"Error insertando {home} vs {away}: {e}")

    conn.commit()
    conn.close()
    print("Sincronizacion manual avanzada completada.")

if __name__ == "__main__":
    manual_sync()
