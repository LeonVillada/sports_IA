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

    # Resultados a inyectar
    results = [
        # Premier League
        ("2026-04-24", "Premier League", "Sunderland", "Nott'm Forest", 0, 5),
        ("2026-04-25", "Premier League", "Fulham", "Aston Villa", 1, 0),
        ("2026-04-25", "Premier League", "Liverpool", "Crystal Palace", 3, 1),
        ("2026-04-25", "Premier League", "West Ham", "Everton", 2, 1),
        ("2026-04-25", "Premier League", "Wolves", "Tottenham", 0, 1),
        ("2026-04-25", "Premier League", "Arsenal", "Newcastle", 1, 0),
        
        # La Liga
        ("2026-04-24", "La Liga", "Real Betis", "Real Madrid", 1, 1),
        ("2026-04-25", "La Liga", "Alaves", "Mallorca", 2, 1),
        ("2026-04-25", "La Liga", "Getafe", "Barcelona", 0, 2),
        ("2026-04-25", "La Liga", "Valencia", "Girona", 2, 1),
        ("2026-04-25", "La Liga", "Atletico Madrid", "Athletic Club", 3, 2),
        ("2026-04-26", "La Liga", "Rayo Vallecano", "Real Sociedad", 3, 3),
        ("2026-04-26", "La Liga", "Osasuna", "Sevilla", 2, 1),
        ("2026-04-26", "La Liga", "Villarreal", "Celta Vigo", 2, 1),

        # Bundesliga
        ("2026-04-24", "Bundesliga", "RB Leipzig", "Union Berlin", 3, 1),
        ("2026-04-25", "Bundesliga", "Heidenheim", "St Pauli", 2, 0),
        ("2026-04-25", "Bundesliga", "Augsburg", "Ein Frankfurt", 1, 1),
        ("2026-04-25", "Bundesliga", "FC Koln", "Leverkusen", 1, 2),
        ("2026-04-25", "Bundesliga", "Mainz", "Bayern Munich", 3, 4),
        ("2026-04-25", "Bundesliga", "Wolfsburg", "M'gladbach", 0, 0),
        ("2026-04-26", "Bundesliga", "VfB Stuttgart", "Werder Bremen", 1, 1),
        ("2026-04-26", "Bundesliga", "Dortmund", "Freiburg", 4, 0),

        # Serie A
        ("2026-04-24", "Serie A", "Napoli", "Cremonese", 4, 0),
        ("2026-04-25", "Serie A", "Parma", "Pisa", 1, 0),
        ("2026-04-25", "Serie A", "Bologna", "Roma", 0, 2),
        ("2026-04-25", "Serie A", "Verona", "Lecce", 0, 0),
        ("2026-04-26", "Serie A", "Fiorentina", "Sassuolo", 0, 0),
        ("2026-04-26", "Serie A", "Genoa", "Como", 0, 2),
        ("2026-04-26", "Serie A", "Torino", "Inter", 2, 2),
        ("2026-04-26", "Serie A", "Milan", "Juventus", 0, 0),

        # Ligue 1
        ("2026-04-24", "Ligue 1", "Brest", "Lens", 3, 3),
        ("2026-04-25", "Ligue 1", "Lyon", "Auxerre", 3, 2),
        ("2026-04-25", "Ligue 1", "Angers", "Paris SG", 0, 3),
        ("2026-04-25", "Ligue 1", "Toulouse", "Monaco", 2, 2),
        ("2026-04-26", "Ligue 1", "Lorient", "Strasbourg", 2, 3),
        ("2026-04-26", "Ligue 1", "Rennes", "Nantes", 2, 1),
        ("2026-04-26", "Ligue 1", "Marseille", "Nice", 1, 1),
    ]

    for date, league_name, home, away, hg, ag in results:
        try:
            league_id = league_map.get(league_name)
            
            # Obtener o crear equipos
            cursor.execute("SELECT id FROM teams WHERE name = %s", (home,))
            res = cursor.fetchone()
            if res: home_id = res[0]
            else:
                cursor.execute("INSERT INTO teams (league_id, name) VALUES (%s, %s)", (league_id, home))
                home_id = cursor.lastrowid
            
            cursor.execute("SELECT id FROM teams WHERE name = %s", (away,))
            res = cursor.fetchone()
            if res: away_id = res[0]
            else:
                cursor.execute("INSERT INTO teams (league_id, name) VALUES (%s, %s)", (league_id, away))
                away_id = cursor.lastrowid

            # Insertar partido
            sql = """
                INSERT IGNORE INTO matches (date, league_id, home_team_id, away_team_id, home_goals, away_goals, status, season) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (date, league_id, home_id, away_id, hg, ag, 'finished', '2526'))
            
        except Exception as e:
            print(f"Error insertando {home} vs {away}: {e}")

    conn.commit()
    conn.close()
    print("✅ Sincronización manual completada.")

if __name__ == "__main__":
    manual_sync()
