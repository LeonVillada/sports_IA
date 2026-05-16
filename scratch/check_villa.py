import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection
conn = create_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute('USE sports_ai_db')
cursor.execute("""
    SELECT m.id, m.date, t1.name as home, t2.name as away, m.home_goals, m.away_goals, m.status 
    FROM matches m 
    JOIN teams t1 ON m.home_team_id = t1.id 
    JOIN teams t2 ON m.away_team_id = t2.id 
    WHERE t1.name LIKE '%Aston Villa%' OR t2.name LIKE '%Aston Villa%' 
    ORDER BY m.date DESC LIMIT 5
""")
for row in cursor.fetchall():
    print(row)
conn.close()
