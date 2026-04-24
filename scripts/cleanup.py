from scripts.db_manager import create_connection

def super_cleanup():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    print("🧹 Iniciando Saneamiento Total...")

    # 1. Mapeo de códigos a nombres reales
    mapping = {
        'E0': ('Premier League', 'Inglaterra'),
        'SP1': ('La Liga', 'España'),
        'I1': ('Serie A', 'Italia'),
        'D1': ('Bundesliga', 'Alemania'),
        'F1': ('Ligue 1', 'Francia')
    }

    # 2. Normalizar nombres antes de fusionar
    for code, (name, country) in mapping.items():
        cursor.execute("UPDATE leagues SET name = %s, country = %s WHERE name = %s", (name, country, code))

    # 3. Fusionar Ligas: Mover todos los partidos al ID más bajo de cada nombre
    cursor.execute("SELECT name, MIN(id) as master_id FROM leagues GROUP BY name")
    masters = cursor.fetchall()
    
    for m in masters:
        cursor.execute("UPDATE matches SET league_id = %s WHERE league_id IN (SELECT id FROM leagues WHERE name = %s AND id != %s)", 
                     (m['master_id'], m['name'], m['master_id']))
        cursor.execute("UPDATE teams SET league_id = %s WHERE league_id IN (SELECT id FROM leagues WHERE name = %s AND id != %s)", 
                     (m['master_id'], m['name'], m['master_id']))

    # 4. Eliminar todas las ligas que no sean las "maestras" o que tengan 0 partidos
    cursor.execute("DELETE FROM leagues WHERE id NOT IN (SELECT master_id FROM (SELECT MIN(id) as master_id FROM leagues GROUP BY name) as t)")
    
    # 5. Eliminar ligas que no estén en nuestro mapeo (basura)
    valid_names = [v[0] for v in mapping.values()]
    cursor.execute("DELETE FROM leagues WHERE name NOT IN (%s, %s, %s, %s, %s)" % ("%s", "%s", "%s", "%s", "%s"), tuple(valid_names))

    # 6. Poner la restricción UNIQUE definitiva
    try:
        cursor.execute("ALTER TABLE leagues ADD UNIQUE (name)")
        print("🛡️ Restricción UNIQUE aplicada a Ligas.")
    except: pass

    conn.commit()
    conn.close()
    print("✅ ¡Base de datos limpia! Solo quedan las 5 ligas principales.")

if __name__ == "__main__":
    super_cleanup()
