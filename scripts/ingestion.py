import pandas as pd
import requests
import os
from scripts.db_manager import create_connection
from io import StringIO

# Ligas: E0 (Inglaterra), SP1 (España), I1 (Italia), D1 (Alemania), F1 (Francia)
LEAGUES = ["E0", "SP1", "I1", "D1", "F1"]
# Temporadas: de 2020 a 2024 (2021, 2122, 2223, 2324, 2425)
SEASONS = ["2021", "2122", "2223", "2324", "2425"]

def download_and_import_massive():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor(buffered=True)
    cursor.execute("USE sports_ai_db")
    
    for season in SEASONS:
        for league in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            print(f"Descargando: Temporada {season} | Liga {league}...")
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    df = pd.read_csv(StringIO(response.text))
                    # Filtrar filas vacías
                    df = df.dropna(subset=['HomeTeam', 'AwayTeam'])
                    
                    for index, row in df.iterrows():
                        try:
                            # Liga
                            cursor.execute("INSERT IGNORE INTO leagues (name) VALUES (%s)", (row['Div'],))
                            cursor.execute("SELECT id FROM leagues WHERE name = %s", (row['Div'],))
                            league_id = cursor.fetchone()[0]
                            
                            # Equipos
                            cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, row['HomeTeam']))
                            cursor.execute("SELECT id FROM teams WHERE name = %s", (row['HomeTeam'],))
                            home_id = cursor.fetchone()[0]
                            
                            cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, row['AwayTeam']))
                            cursor.execute("SELECT id FROM teams WHERE name = %s", (row['AwayTeam'],))
                            away_id = cursor.fetchone()[0]
                            
                            # Fecha y Partido
                            date_val = pd.to_datetime(row['Date'], dayfirst=True).strftime('%Y-%m-%d %H:%M:%S')
                            sql_match = "INSERT IGNORE INTO matches (date, league_id, home_team_id, away_team_id, home_goals, away_goals, status, season) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                            cursor.execute(sql_match, (date_val, league_id, home_id, away_id, row['FTHG'], row['FTAG'], 'finished', season))
                            
                            # Obtener ID para las cuotas
                            cursor.execute("SELECT id FROM matches WHERE date=%s AND home_team_id=%s", (date_val, home_id))
                            match_id = cursor.fetchone()[0]
                            
                            # Cuotas de Bet365 (B365)
                            if 'B365H' in row and not pd.isna(row['B365H']):
                                cursor.execute("INSERT IGNORE INTO odds (match_id, bookmaker, home_win_odds, draw_odds, away_win_odds) VALUES (%s, %s, %s, %s, %s)", 
                                             (match_id, 'Bet365', row['B365H'], row['B365D'], row['B365A']))
                        except Exception as e:
                            continue
                    
                    conn.commit()
                    print(f"✅ Éxito: {len(df)} partidos procesados.")
                else:
                    print(f"⚠️ No disponible: {url}")
            except Exception as e:
                print(f"❌ Error en descarga: {e}")

    conn.close()
    print("\n🚀 ¡PROCESO DE CARGA MASIVA FINALIZADO!")

if __name__ == "__main__":
    download_and_import_massive()
