import os
import sys

# Asegurar que reconozca los scripts de lógica
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection
import mysql.connector

def cleanup():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.execute("USE sports_ai_db")
    
    # Mapeo de IDs (Viejo -> Nuevo)
    mapping = {
        7613: 3,    # E0 -> Premier League
        8373: 383,  # SP1 -> La Liga
        8753: 1523, # I1 -> Serie A
        9133: 1903, # D1 -> Bundesliga
        9439: 2209  # F1 -> Ligue 1
    }
    
    print("Iniciando limpieza de base de datos...")
    
    # 1. Actualizar matches que apuntan a ligas con códigos
    for old_id, new_id in mapping.items():
        print(f"Migrando partidos de liga {old_id} a {new_id}...")
        cursor.execute("UPDATE matches SET league_id = %s WHERE league_id = %s", (new_id, old_id))
    
    # 2. Actualizar equipos que apuntan a ligas con códigos
    for old_id, new_id in mapping.items():
        print(f"Actualizando equipos de liga {old_id} a {new_id}...")
        cursor.execute("UPDATE teams SET league_id = %s WHERE league_id = %s", (new_id, old_id))
    
    # 3. Eliminar ligas redundantes
    old_ids_str = ",".join(map(str, mapping.keys()))
    print(f"Eliminando ligas antiguas: {old_ids_str}")
    cursor.execute(f"DELETE FROM leagues WHERE id IN ({old_ids_str})")
    
    # 4. Deduplicar partidos
    # Un partido es duplicado si tiene la misma fecha, local y visitante.
    # Conservamos el que tenga el ID más bajo.
    print("Buscando y eliminando partidos duplicados...")
    cursor.execute("""
        DELETE m1 FROM matches m1
        INNER JOIN matches m2 
        WHERE m1.id > m2.id 
          AND m1.date = m2.date 
          AND m1.home_team_id = m2.home_team_id 
          AND m1.away_team_id = m2.away_team_id
    """)
    print(f"Partidos eliminados: {cursor.rowcount}")
    
    # 5. Añadir restricción UNIQUE para evitar futuros duplicados
    print("Añadiendo índice UNIQUE a la tabla matches...")
    try:
        cursor.execute("ALTER TABLE matches ADD UNIQUE INDEX idx_match_unique (date, home_team_id, away_team_id)")
    except mysql.connector.Error as err:
        print(f"Aviso al añadir índice UNIQUE: {err}")
    
    conn.commit()
    conn.close()
    print("LIMPIEZA COMPLETADA CON ÉXITO.")

if __name__ == "__main__":
    cleanup()
