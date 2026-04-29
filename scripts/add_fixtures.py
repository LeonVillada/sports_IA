from scripts.db_manager import create_connection
import mysql.connector

def add_manual_fixtures():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.execute("USE sports_ai_db")

    fixtures = [
        # Premier League
        ("Premier League", "Leeds", "Burnley", "2026-05-01 20:00:00"),
        ("Premier League", "Bournemouth", "Crystal Palace", "2026-05-02 15:00:00"),
        ("Premier League", "Brentford", "West Ham", "2026-05-02 15:00:00"),
        ("Premier League", "Newcastle", "Brighton", "2026-05-02 15:00:00"),
        ("Premier League", "Wolves", "Sunderland", "2026-05-02 15:00:00"),
        ("Premier League", "Arsenal", "Fulham", "2026-05-02 17:30:00"),
        ("Premier League", "Man United", "Liverpool", "2026-05-03 15:30:00"),
        ("Premier League", "Aston Villa", "Tottenham", "2026-05-03 19:00:00"),
        ("Premier League", "Chelsea", "Nott'm Forest", "2026-05-04 15:00:00"),

        # La Liga
        ("La Liga", "Villarreal", "Levante", "2026-05-02 16:00:00"),
        ("La Liga", "Valencia", "Atl Madrid", "2026-05-02 18:30:00"),
        ("La Liga", "Alaves", "Ath Bilbao", "2026-05-02 21:00:00"),
        ("La Liga", "Osasuna", "Barcelona", "2026-05-03 21:00:00"),

        # Serie A
        ("Serie A", "Udinese", "Torino", "2026-05-02 15:00:00"),
        ("Serie A", "Como", "Napoli", "2026-05-02 18:00:00"),
        ("Serie A", "Atalanta", "Genoa", "2026-05-02 20:45:00"),

        # Bundesliga
        ("Bundesliga", "Bayern Munich", "Heidenheim", "2026-05-02 15:30:00"),
        ("Bundesliga", "Frankfurt", "Hamburg", "2026-05-02 15:30:00"),
        ("Bundesliga", "Hoffenheim", "Stuttgart", "2026-05-02 15:30:00"),
        ("Bundesliga", "Union Berlin", "FC Koln", "2026-05-02 15:30:00"),
        ("Bundesliga", "Werder Bremen", "Augsburg", "2026-05-02 15:30:00"),
        ("Bundesliga", "Leverkusen", "RB Leipzig", "2026-05-02 18:30:00"),

        # Ligue 1
        ("Ligue 1", "Nantes", "Marseille", "2026-05-02 17:00:00"),
        ("Ligue 1", "Paris SG", "Lorient", "2026-05-02 21:00:00"),
        ("Ligue 1", "Metz", "Monaco", "2026-05-03 15:00:00"),
        ("Ligue 1", "Nice", "Lens", "2026-05-03 17:05:00"),
    ]

    print("Insertando fixtures manuales...")
    for league_name, home_name, away_name, date_str in fixtures:
        try:
            # Asegurar liga
            cursor.execute("INSERT IGNORE INTO leagues (name) VALUES (%s)", (league_name,))
            cursor.execute("SELECT id FROM leagues WHERE name = %s", (league_name,))
            league_id = cursor.fetchone()[0]

            # Asegurar equipos
            for t_name in [home_name, away_name]:
                cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, t_name))
            
            cursor.execute("SELECT id FROM teams WHERE name = %s", (home_name,))
            home_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM teams WHERE name = %s", (away_name,))
            away_id = cursor.fetchone()[0]

            # Insertar partido
            sql = """
                INSERT INTO matches (date, league_id, home_team_id, away_team_id, status, season)
                VALUES (%s, %s, %s, %s, 'scheduled', '2526')
                ON DUPLICATE KEY UPDATE date=VALUES(date), status=VALUES(status)
            """
            cursor.execute(sql, (date_str, league_id, home_id, away_id))
            
            # Opcional: Añadir cuotas ficticias si no hay para que el modelo tenga algo
            # (Aunque el modelo usa históricos, la UI podría mostrar cuotas)
            
        except Exception as e:
            print(f"Error insertando {home_name} vs {away_name}: {e}")

    conn.commit()
    conn.close()
    print("Fixtures manuales insertados correctamente.")

if __name__ == "__main__":
    add_manual_fixtures()
