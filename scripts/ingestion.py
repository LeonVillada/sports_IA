import pandas as pd
import requests
import random
import os
from scripts.db_manager import create_connection
from scripts.config import load_config, save_config
from io import StringIO
from datetime import datetime, timedelta

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
SEASONS = ["2425", "2526"]

# Cache de proxies para no pedirlos en cada llamada
_proxy_cache = []

def _get_proxies():
    """Obtiene lista de proxies HTTP gratuitos de ProxyScrape."""
    global _proxy_cache
    if _proxy_cache:
        return _proxy_cache
    try:
        r = requests.get(
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all',
            timeout=10
        )
        proxies = [p.strip() for p in r.text.strip().split('\r\n') if p.strip()]
        random.shuffle(proxies)
        _proxy_cache = proxies
        print(f"[PROXY] Cargados {len(proxies)} proxies.")
        return proxies
    except Exception as e:
        print(f"[PROXY] No se pudo cargar lista de proxies: {e}")
        return []

def _is_valid_csv(text):
    """Verifica que la respuesta sea un CSV real y no una página HTML de bloqueo."""
    if not text:
        return False
    stripped = text.strip()
    if stripped.startswith('<') or 'DOCTYPE' in stripped or 'Coljuegos' in stripped or 'mail-in-a-box' in stripped:
        return False
    return True

def fetch_csv(url, max_proxies=40, timeout=7):
    """
    Fetcher robusto: intenta conexión directa primero.
    Si falla o devuelve HTML bloqueado, rota por proxies automáticamente.
    Devuelve el texto del CSV o None si todo falla.
    """
    # 1. Intentar conexión directa
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and _is_valid_csv(r.text):
            print(f"[OK] Descarga directa: {url}")
            return r.text
        else:
            print(f"[WARN] Descarga directa bloqueada (status={r.status_code}, es HTML). Usando proxies...")
    except Exception as e:
        print(f"[WARN] Descarga directa falló: {e}. Usando proxies...")

    # 2. Rotar por proxies
    proxies_list = _get_proxies()
    if not proxies_list:
        print("[ERROR] Sin proxies disponibles.")
        return None

    for i, proxy_ip in enumerate(proxies_list[:max_proxies]):
        proxy_conf = {"http": f"http://{proxy_ip}", "https": f"http://{proxy_ip}"}
        try:
            r = requests.get(url, proxies=proxy_conf, timeout=timeout)
            if r.status_code == 200 and _is_valid_csv(r.text):
                print(f"[OK] Proxy {proxy_ip} funcionó para: {url}")
                return r.text
        except Exception:
            pass

    print(f"[ERROR] No se pudo descargar {url} con ninguno de los {max_proxies} proxies probados.")
    return None


def cleanup_stale_scheduled_matches(conn):
    """
    Marca como 'played' (sin goles) los partidos con status='scheduled'
    cuya fecha ya pasó. Así no aparecen en pronósticos y no generan ruido.
    Esto es un fallback para cuando el servidor no puede descargar resultados.
    """
    cursor = conn.cursor()
    cursor.execute("USE sports_ai_db")
    cursor.execute("""
        UPDATE matches
        SET status = 'played_no_data'
        WHERE status = 'scheduled' AND date < NOW() - INTERVAL 2 HOUR
    """)
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    if affected > 0:
        print(f"[CLEANUP] {affected} partido(s) pasado(s) con status 'scheduled' -> marcado(s) como 'played_no_data'.")
    return affected


def download_and_import_massive():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor(buffered=True)
    cursor.execute("USE sports_ai_db")

    config = load_config()
    # Determinar fecha de inicio desde el último partido con goles en BD
    try:
        cursor.execute("SELECT MAX(date) FROM matches WHERE home_goals IS NOT NULL")
        db_last_match = cursor.fetchone()[0]
        if db_last_match:
            safe_date_obj = db_last_match - timedelta(days=3)
            safe_date_str = safe_date_obj.strftime("%Y-%m-%d")
            print(f"[SYNC] Último partido con goles: {db_last_match.strftime('%Y-%m-%d')}. Buscando desde: {safe_date_str}")
        else:
            last_sync_obj = datetime.strptime(config.get("last_sync_date", "2024-01-01"), "%Y-%m-%d")
            safe_date_str = (last_sync_obj - timedelta(days=3)).strftime("%Y-%m-%d")
            print(f"[SYNC] Sin goles en BD. Usando config: {safe_date_str}")
    except Exception as e:
        print(f"[SYNC] Error leyendo BD: {e}. Usando fallback.")
        safe_date_str = config.get("last_sync_date", "2024-01-01")

    updated_count = 0
    for season in SEASONS:
        for league in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            print(f"Descargando: Temporada {season} | Liga {league}...")

            csv_text = fetch_csv(url)
            if not csv_text:
                print(f"SKIP: No se pudo obtener {league} ({season})")
                continue

            try:
                df = pd.read_csv(StringIO(csv_text))
                df.rename(columns={df.columns[0]: 'Div'}, inplace=True)
                df = df.dropna(subset=['HomeTeam', 'AwayTeam'])
                df['Date_Parsed'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Date_Parsed'])

                original_len = len(df)
                df = df[df['Date_Parsed'] >= safe_date_str]
                print(f"  -> Procesando {len(df)} partidos (omitidos {original_len - len(df)} anteriores).")

                for index, row in df.iterrows():
                    try:
                        league_code = row['Div']
                        league_name = LEAGUE_MAP.get(league_code, league_code)

                        cursor.execute("INSERT IGNORE INTO leagues (name) VALUES (%s)", (league_name,))
                        cursor.execute("SELECT id FROM leagues WHERE name = %s", (league_name,))
                        league_id = cursor.fetchone()[0]

                        cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, row['HomeTeam']))
                        cursor.execute("SELECT id FROM teams WHERE name = %s", (row['HomeTeam'],))
                        home_id = cursor.fetchone()[0]

                        cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, row['AwayTeam']))
                        cursor.execute("SELECT id FROM teams WHERE name = %s", (row['AwayTeam'],))
                        away_id = cursor.fetchone()[0]

                        date_val = row['Date_Parsed'].strftime('%Y-%m-%d %H:%M:%S')
                        date_only = row['Date_Parsed'].strftime('%Y-%m-%d')

                        def safe_get(col):
                            v = row.get(col)
                            try:
                                return None if pd.isna(v) else v
                            except:
                                return None

                        stats = {
                            'ht_home_goals': safe_get('HTHG'), 'ht_away_goals': safe_get('HTAG'),
                            'home_shots': safe_get('HS'), 'away_shots': safe_get('AS'),
                            'home_shots_on_target': safe_get('HST'), 'away_shots_on_target': safe_get('AST'),
                            'home_corners': safe_get('HC'), 'away_corners': safe_get('AC'),
                            'home_fouls': safe_get('HF'), 'away_fouls': safe_get('AF'),
                            'home_yellow_cards': safe_get('HY'), 'away_yellow_cards': safe_get('AY'),
                            'home_red_cards': safe_get('HR'), 'away_red_cards': safe_get('AR'),
                        }

                        cursor.execute("""
                            SELECT id FROM matches
                            WHERE DATE(date) = %s AND home_team_id = %s AND away_team_id = %s
                        """, (date_only, home_id, away_id))
                        existing = cursor.fetchone()

                        fthg = safe_get('FTHG')
                        ftag = safe_get('FTAG')

                        if existing:
                            match_id = existing[0]
                            cursor.execute("""
                                UPDATE matches SET
                                    home_goals=%s, away_goals=%s,
                                    ht_home_goals=%s, ht_away_goals=%s,
                                    home_shots=%s, away_shots=%s,
                                    home_shots_on_target=%s, away_shots_on_target=%s,
                                    home_corners=%s, away_corners=%s,
                                    home_fouls=%s, away_fouls=%s,
                                    home_yellow_cards=%s, away_yellow_cards=%s,
                                    home_red_cards=%s, away_red_cards=%s,
                                    status='finished', season=%s
                                WHERE id=%s
                            """, (
                                fthg, ftag,
                                stats['ht_home_goals'], stats['ht_away_goals'],
                                stats['home_shots'], stats['away_shots'],
                                stats['home_shots_on_target'], stats['away_shots_on_target'],
                                stats['home_corners'], stats['away_corners'],
                                stats['home_fouls'], stats['away_fouls'],
                                stats['home_yellow_cards'], stats['away_yellow_cards'],
                                stats['home_red_cards'], stats['away_red_cards'],
                                season, match_id
                            ))
                            updated_count += 1
                        else:
                            cursor.execute("""
                                INSERT INTO matches (
                                    date, league_id, home_team_id, away_team_id, home_goals, away_goals,
                                    ht_home_goals, ht_away_goals, home_shots, away_shots,
                                    home_shots_on_target, away_shots_on_target, home_corners, away_corners,
                                    home_fouls, away_fouls, home_yellow_cards, away_yellow_cards,
                                    home_red_cards, away_red_cards, status, season
                                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """, (
                                date_val, league_id, home_id, away_id, fthg, ftag,
                                stats['ht_home_goals'], stats['ht_away_goals'],
                                stats['home_shots'], stats['away_shots'],
                                stats['home_shots_on_target'], stats['away_shots_on_target'],
                                stats['home_corners'], stats['away_corners'],
                                stats['home_fouls'], stats['away_fouls'],
                                stats['home_yellow_cards'], stats['away_yellow_cards'],
                                stats['home_red_cards'], stats['away_red_cards'],
                                'finished', season
                            ))
                            cursor.execute("SELECT LAST_INSERT_ID()")
                            match_id = cursor.fetchone()[0]
                            updated_count += 1

                        # Cuotas B365
                        b365h = safe_get('B365H')
                        b365d = safe_get('B365D')
                        b365a = safe_get('B365A')
                        if b365h and b365d and b365a:
                            cursor.execute("""
                                INSERT IGNORE INTO odds (match_id, bookmaker, home_win_odds, draw_odds, away_win_odds)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (match_id, 'Bet365', b365h, b365d, b365a))

                        # Cuotas Hándicap Asiático
                        ah_line = safe_get('AvgAH') or safe_get('BbAvAH')
                        ah_home = safe_get('AvgAHH') or safe_get('BbAvAHH')
                        ah_away = safe_get('AvgAHA') or safe_get('BbAvAHA')
                        if ah_line and ah_home:
                            cursor.execute("""
                                UPDATE odds SET handicap_line=%s, home_handicap_odds=%s, away_handicap_odds=%s
                                WHERE match_id=%s AND bookmaker='Bet365'
                            """, (ah_line, ah_home, ah_away, match_id))

                    except Exception as e:
                        print(f"Error fila {index}: {e}")
                        continue

                conn.commit()
                print(f"OK: {len(df)} partidos procesados para {league} ({season}).")

            except Exception as e:
                print(f"ERROR parseando CSV {league} ({season}): {e}")

    print(f"\n[SYNC] PROCESO FINALIZADO. {updated_count} partidos actualizados/insertados.")
    conn.close()


def sync_fixtures():
    """
    Descarga e importa los próximos partidos (fixtures) con fallback a proxy.
    
    Retorna un diccionario con el resultado:
      - status: "ok" | "empty" | "error"
      - fixtures_found: número de fixtures procesados
      - message: descripción del resultado
    """
    result = {"status": "error", "fixtures_found": 0, "message": ""}

    conn = create_connection()
    if not conn:
        result["message"] = "No se pudo conectar a la base de datos."
        return result

    cursor = conn.cursor(buffered=True)
    cursor.execute("USE sports_ai_db")

    url = "https://www.football-data.co.uk/fixtures.csv"
    print("Sincronizando próximos partidos (Fixtures)...")

    csv_text = fetch_csv(url)
    if not csv_text:
        msg = "No se pudo obtener fixtures.csv. Los pronósticos pueden estar desactualizados."
        print(f"WARN: {msg}")
        cursor.close()
        conn.close()
        result["message"] = msg
        result["status"] = "error"
        return result

    try:
        df = pd.read_csv(StringIO(csv_text))
        df.rename(columns={df.columns[0]: 'Div'}, inplace=True)
        df = df[df['Div'].isin(LEAGUES)]
        new_fixtures = 0

        for _, row in df.iterrows():
            try:
                league_name = LEAGUE_MAP.get(row['Div'])
                if not league_name:
                    continue

                cursor.execute("INSERT IGNORE INTO leagues (name) VALUES (%s)", (league_name,))
                cursor.execute("SELECT id FROM leagues WHERE name = %s", (league_name,))
                res = cursor.fetchone()
                if not res:
                    continue
                league_id = res[0]

                for team_name in [row['HomeTeam'], row['AwayTeam']]:
                    cursor.execute("INSERT IGNORE INTO teams (league_id, name) VALUES (%s, %s)", (league_id, team_name))

                cursor.execute("SELECT id FROM teams WHERE name = %s", (row['HomeTeam'],))
                home_res = cursor.fetchone()
                cursor.execute("SELECT id FROM teams WHERE name = %s", (row['AwayTeam'],))
                away_res = cursor.fetchone()
                if not home_res or not away_res:
                    continue
                home_id = home_res[0]
                away_id = away_res[0]

                date_val = pd.to_datetime(row['Date'], dayfirst=True).strftime('%Y-%m-%d')
                if 'Time' in row and pd.notna(row['Time']):
                    date_val += f" {row['Time']}:00"
                else:
                    date_val += " 15:00:00"

                cursor.execute("""
                    INSERT INTO matches (date, league_id, home_team_id, away_team_id, status)
                    VALUES (%s, %s, %s, %s, 'scheduled')
                    ON DUPLICATE KEY UPDATE status=IF(status='finished', 'finished', 'scheduled'), date=VALUES(date)
                """, (date_val, league_id, home_id, away_id))
                new_fixtures += 1

                # Obtener ID y cuotas
                cursor.execute("SELECT id FROM matches WHERE DATE(date)=DATE(%s) AND home_team_id=%s AND away_team_id=%s",
                               (date_val, home_id, away_id))
                match_res = cursor.fetchone()
                if match_res and 'B365H' in row and pd.notna(row.get('B365H')):
                    match_id = match_res[0]
                    cursor.execute("""
                        INSERT INTO odds (match_id, bookmaker, home_win_odds, draw_odds, away_win_odds)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE home_win_odds=VALUES(home_win_odds),
                            draw_odds=VALUES(draw_odds), away_win_odds=VALUES(away_win_odds)
                    """, (match_id, 'Bet365', row['B365H'], row['B365D'], row['B365A']))

            except Exception as e:
                continue

        conn.commit()

        if new_fixtures == 0:
            msg = (
                "No se encontraron fixtures futuros en las ligas rastreadas. "
                "Es posible que la temporada 2024-25 haya finalizado. "
                "Los datos estarán disponibles cuando comience la temporada 2025-26 (agosto-septiembre 2025)."
            )
            print(f"[FIXTURES] {msg}")
            result["status"] = "empty"
            result["message"] = msg
        else:
            msg = f"{new_fixtures} fixtures sincronizados correctamente."
            print(f"OK: {msg}")
            result["status"] = "ok"
            result["message"] = msg

        result["fixtures_found"] = new_fixtures

    except Exception as e:
        msg = f"ERROR parseando fixtures.csv: {e}"
        print(msg)
        result["status"] = "error"
        result["message"] = msg
    finally:
        cursor.close()
        conn.close()

    return result


if __name__ == "__main__":
    download_and_import_massive()
    sync_fixtures()
