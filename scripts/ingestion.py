import pandas as pd
import requests
import os
from scripts.db_manager import create_connection
from io import StringIO

# Mapeo de códigos de football-data.co.uk a nombres reales
LEAGUE_MAP = {
    "E0": "Premier League",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
    "E1": "Championship"
}

LEAGUES = ["E0", "SP1", "I1", "D1", "F1", "E1"]
# Solo las temporadas más recientes para alimentar el sistema hacia el futuro
SEASONS = ["2425", "2526"]

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
                            # Liga (Mapear código a nombre real)
                            league_code = row['Div']
                            league_name = LEAGUE_MAP.get(league_code, league_code)
                            
                            cursor.execute("INSERT IGNORE INTO leagues (name) VALUES (%s)", (league_name,))
                            cursor.execute("SELECT id FROM leagues WHERE name = %s", (league_name,))
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
                            
                            # Estadísticas adicionales (usando .get() o verificando existencia)
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
                            # Reemplazar NaNs por None para MySQL
                            stats = {k: (None if pd.isna(v) else v) for k, v in stats.items()}

                            sql_match = """
                                INSERT INTO matches (
                                    date, league_id, home_team_id, away_team_id, home_goals, away_goals, 
                                    ht_home_goals, ht_away_goals, home_shots, away_shots, 
                                    home_shots_on_target, away_shots_on_target, home_corners, away_corners, 
                                    home_fouls, away_fouls, home_yellow_cards, away_yellow_cards, 
                                    home_red_cards, away_red_cards, status, season
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON DUPLICATE KEY UPDATE 
                                    home_goals=VALUES(home_goals), away_goals=VALUES(away_goals),
                                    ht_home_goals=VALUES(ht_home_goals), ht_away_goals=VALUES(ht_away_goals),
                                    home_shots=VALUES(home_shots), away_shots=VALUES(away_shots),
                                    home_shots_on_target=VALUES(home_shots_on_target), away_shots_on_target=VALUES(away_shots_on_target),
                                    home_corners=VALUES(home_corners), away_corners=VALUES(away_corners),
                                    home_fouls=VALUES(home_fouls), away_fouls=VALUES(away_fouls),
                                    home_yellow_cards=VALUES(home_yellow_cards), away_yellow_cards=VALUES(away_yellow_cards),
                                    home_red_cards=VALUES(home_red_cards), away_red_cards=VALUES(away_red_cards)
                            """
                            cursor.execute(sql_match, (
                                date_val, league_id, home_id, away_id, row['FTHG'], row['FTAG'],
                                stats['ht_home_goals'], stats['ht_away_goals'], stats['home_shots'], stats['away_shots'],
                                stats['home_shots_on_target'], stats['away_shots_on_target'], stats['home_corners'], stats['away_corners'],
                                stats['home_fouls'], stats['away_fouls'], stats['home_yellow_cards'], stats['away_yellow_cards'],
                                stats['home_red_cards'], stats['away_red_cards'], 'finished', season
                            ))
                            
                            # Obtener ID para las cuotas
                            cursor.execute("SELECT id FROM matches WHERE date=%s AND home_team_id=%s", (date_val, home_id))
                            match_id = cursor.fetchone()[0]
                            
                            # Cuotas de Bet365 (B365)
                            if 'B365H' in row and not pd.isna(row['B365H']) and not pd.isna(row['B365D']) and not pd.isna(row['B365A']):
                                cursor.execute("INSERT IGNORE INTO odds (match_id, bookmaker, home_win_odds, draw_odds, away_win_odds) VALUES (%s, %s, %s, %s, %s)", 
                                             (match_id, 'Bet365', row['B365H'], row['B365D'], row['B365A']))
                            
                            # Cuotas de Hándicap Asiático (Promedio)
                            ah_line = row.get('AvgAH') or row.get('BbAvAH')
                            ah_home = row.get('AvgAHH') or row.get('BbAvAHH')
                            ah_away = row.get('AvgAHA') or row.get('BbAvAHA')
                            
                            if not pd.isna(ah_line) and not pd.isna(ah_home):
                                cursor.execute("""
                                    UPDATE odds SET handicap_line=%s, home_handicap_odds=%s, away_handicap_odds=%s 
                                    WHERE match_id=%s AND bookmaker='Bet365'
                                """, (ah_line, ah_home, ah_away, match_id))
                        except Exception as e:
                            continue
                    
                    conn.commit()
                    print(f"OK: {len(df)} partidos procesados.")
                else:
                    print(f"WARN: No disponible: {url}")
            except Exception as e:
                print(f"ERROR en descarga: {e}")

    conn.close()
    print("\nPROCESO DE CARGA MASIVA FINALIZADO!")

def sync_fixtures():
    """Descarga e importa los próximos partidos (fixtures)"""
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor(buffered=True)
    cursor.execute("USE sports_ai_db")
    
    url = "https://www.football-data.co.uk/fixtures.csv"
    print("Sincronizando próximos partidos (Fixtures)...")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Leer el CSV y forzar el nombre de la primera columna (evita errores de BOM)
            df = pd.read_csv(StringIO(response.text))
            df.rename(columns={df.columns[0]: 'Div'}, inplace=True)
            
            # Filtrar solo nuestras 5 ligas
            df = df[df['Div'].isin(LEAGUES)]
            
            for _, row in df.iterrows():
                try:
                    league_name = LEAGUE_MAP.get(row['Div'])
                    cursor.execute("SELECT id FROM leagues WHERE name = %s", (league_name,))
                    league_id = cursor.fetchone()[0]
                    
                    # Equipos (Asegurar que existan)
                    for team_name in [row['HomeTeam'], row['AwayTeam']]:
                        cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, team_name))
                    
                    cursor.execute("SELECT id FROM teams WHERE name = %s", (row['HomeTeam'],))
                    home_id = cursor.fetchone()[0]
                    cursor.execute("SELECT id FROM teams WHERE name = %s", (row['AwayTeam'],))
                    away_id = cursor.fetchone()[0]
                    
                    # Fecha
                    date_val = pd.to_datetime(row['Date'], dayfirst=True).strftime('%Y-%m-%d')
                    if 'Time' in row:
                        date_val += f" {row['Time']}:00"
                    
                    # Insertar partido como 'scheduled'
                    sql_match = """
                        INSERT INTO matches (date, league_id, home_team_id, away_team_id, status)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE status=VALUES(status), date=VALUES(date)
                    """
                    cursor.execute(sql_match, (date_val, league_id, home_id, away_id, 'scheduled'))
                    
                    # Obtener ID para cuotas
                    cursor.execute("SELECT id FROM matches WHERE date=%s AND home_team_id=%s", (date_val, home_id))
                    match_id = cursor.fetchone()[0]
                    
                    # Cuotas iniciales (B365)
                    if 'B365H' in row and not pd.isna(row['B365H']):
                        cursor.execute("""
                            INSERT INTO odds (match_id, bookmaker, home_win_odds, draw_odds, away_win_odds) 
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE home_win_odds=VALUES(home_win_odds), draw_odds=VALUES(draw_odds), away_win_odds=VALUES(away_win_odds)
                        """, (match_id, 'Bet365', row['B365H'], row['B365D'], row['B365A']))
                
                except Exception as e:
                    continue
            
            conn.commit()
            print("OK: Fixtures actualizados.")
        else:
            print("WARN: No se pudo descargar fixtures.csv")
    except Exception as e:
        print(f"ERROR Fixtures: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    download_and_import_massive()
    sync_fixtures()
