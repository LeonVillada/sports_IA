import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection
conn = create_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute('USE sports_ai_db')

cursor.execute("""
    SELECT m.id, m.date, l.name as league 
    FROM matches m 
    JOIN leagues l ON m.league_id = l.id 
    WHERE DATE(m.date) = '2026-05-15'
""")
for row in cursor.fetchall():
    print(row)
conn.close()
