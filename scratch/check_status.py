from scripts.db_manager import create_connection

conn = create_connection()
cursor = conn.cursor()
cursor.execute('USE sports_ai_db')
cursor.execute("SELECT status, COUNT(id) FROM matches GROUP BY status")
for row in cursor.fetchall():
    print(row)
conn.close()
