import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection
conn = create_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute('USE sports_ai_db')

query = """
    SELECT DISTINCT m.date, l.name as league, t1.name as home, t2.name as away, 
           m.home_goals, m.away_goals, 
           m.status,
           (DATE(m.date) = '2026-05-15') as is_today
    FROM matches m
    JOIN leagues l ON m.league_id = l.id
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    LEFT JOIN odds o ON m.id = o.match_id
    WHERE l.name IN ('Premier League', 'La Liga', 'Bundesliga', 'Ligue 1', 'Serie A')
    ORDER BY (DATE(m.date) = '2026-05-15') DESC, (m.status = 'finished') DESC, m.date DESC 
    LIMIT 5
"""
cursor.execute(query)
results = cursor.fetchall()
print(f"Total results: {len(results)}")
print(f"{'Fecha':<16} | {'Today':<5} | {'Status':<10} | {'Home':<20} | {'Away':<20} | {'Score'}")
print("-" * 100)
for m in results:
    date_str = m['date'].strftime('%Y-%m-%d %H:%M')
    score = f"{m['home_goals']}-{m['away_goals']}" if m['status'] == 'finished' else "vs"
    print(f"{date_str:<16} | {m['is_today']:<5} | {m['status']:<10} | {m['home']:<20} | {m['away']:<20} | {score}")

conn.close()
