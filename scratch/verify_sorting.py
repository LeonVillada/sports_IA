import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.db_manager import create_connection
conn = create_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute('USE sports_ai_db')

query = """
    SELECT m.date, t1.name as home, t2.name as away, m.status, m.home_goals, m.away_goals,
           (DATE(m.date) = '2026-05-15') as is_today,
           (m.status = 'finished') as is_finished
    FROM matches m
    JOIN leagues l ON m.league_id = l.id
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    WHERE l.name IN ('Premier League', 'La Liga', 'Bundesliga', 'Ligue 1', 'Serie A')
    ORDER BY is_today DESC, is_finished DESC, m.date DESC 
    LIMIT 15
"""
cursor.execute(query)
print(f"{'Fecha':<12} | {'T':<2} | {'F':<2} | {'Status':<10} | {'Home':<20} | {'Away':<20} | {'Score'}")
print("-" * 100)
for m in cursor.fetchall():
    date_str = m['date'].strftime('%Y-%m-%d')
    score = f"{m['home_goals']}-{m['away_goals']}" if m['status'] == 'finished' else "vs"
    print(f"{date_str:<12} | {m['is_today']:<2} | {m['is_finished']:<2} | {m['status']:<10} | {m['home']:<20} | {m['away']:<20} | {score}")

conn.close()
