import os
import sys
import pandas as pd
import requests
from io import StringIO

# Asegurar que reconozca los scripts de lógica
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection

# Ligas y Temporadas Históricas
LEAGUE_MAP = {
    "E0": "Premier League",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1"
}
SEASONS = ["2021", "2122", "2223", "2324", "2425", "2526"]

def enrich_data():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor(buffered=True)
    cursor.execute("USE sports_ai_db")
    
    for season in SEASONS:
        for code, name in LEAGUE_MAP.items():
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
            print(f"Enriqueciendo: Temporada {season} | Liga {name}...")
            
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    df = pd.read_csv(StringIO(response.text))
                    df = df.dropna(subset=['HomeTeam', 'AwayTeam'])
                    
                    for _, row in df.iterrows():
                        try:
                            # 1. Obtener IDs de equipos
                            cursor.execute("SELECT id FROM teams WHERE name = %s", (row['HomeTeam'],))
                            home_res = cursor.fetchone()
                            cursor.execute("SELECT id FROM teams WHERE name = %s", (row['AwayTeam'],))
                            away_res = cursor.fetchone()
                            
                            if not home_res or not away_res: continue
                            home_id, away_id = home_res[0], away_res[0]
                            
                            # 2. Formatear fecha
                            date_val = pd.to_datetime(row['Date'], dayfirst=True).strftime('%Y-%m-%d %H:%M:%S')
                            
                            # 3. Preparar estadísticas
                            stats = {
                                'ht_home_goals': row.get('HTHG'),
                                'ht_away_goals': row.get('HTAG'),
                                'home_shots': row.get('HS'),
                                'away_shots': row.get('AS'),
                                'home_shots_on_target': row.get('HST'),
                                'away_shots_on_target': row.get('AST'),
                                'home_corners': row.get('HC'),
                                'away_corners': row.get('AC'),
                                'home_fouls': row.get('HF'),
                                'away_fouls': row.get('AF'),
                                'home_yellow_cards': row.get('HY'),
                                'away_yellow_cards': row.get('AY'),
                                'home_red_cards': row.get('HR'),
                                'away_red_cards': row.get('AR')
                            }
                            # Limpiar NaNs
                            stats = {k: (None if pd.isna(v) else v) for k, v in stats.items()}
                            
                            # 4. Actualizar partido (basado en la restricción UNIQUE: date, home_team_id, away_team_id)
                            sql_update = """
                                UPDATE matches SET 
                                    ht_home_goals=%s, ht_away_goals=%s,
                                    home_shots=%s, away_shots=%s, 
                                    home_shots_on_target=%s, away_shots_on_target=%s, 
                                    home_corners=%s, away_corners=%s, 
                                    home_fouls=%s, away_fouls=%s, 
                                    home_yellow_cards=%s, away_yellow_cards=%s, 
                                    home_red_cards=%s, away_red_cards=%s
                                WHERE date=%s AND home_team_id=%s AND away_team_id=%s
                            """
                            cursor.execute(sql_update, (
                                stats['ht_home_goals'], stats['ht_away_goals'],
                                stats['home_shots'], stats['away_shots'],
                                stats['home_shots_on_target'], stats['away_shots_on_target'],
                                stats['home_corners'], stats['away_corners'],
                                stats['home_fouls'], stats['away_fouls'],
                                stats['home_yellow_cards'], stats['away_yellow_cards'],
                                stats['home_red_cards'], stats['away_red_cards'],
                                date_val, home_id, away_id
                            ))
                            
                        except Exception as e:
                            continue
                    
                    conn.commit()
                    print(f"OK: Procesados datos de {name} ({season})")
                else:
                    print(f"WARN: No disponible: {url}")
            except Exception as e:
                print(f"ERROR: {e}")

    conn.close()
    print("\nPROCESO DE ENRIQUECIMIENTO FINALIZADO!")

if __name__ == "__main__":
    enrich_data()
