from scripts.db_manager import create_connection
conn = create_connection()
cursor = conn.cursor()
cursor.execute('USE sports_ai_db')
cursor.execute("SELECT COUNT(*) FROM matches WHERE season='2526'")
print(f"Total matches in 2526: {cursor.fetchone()[0]}")
cursor.execute("SELECT date, home_goals, away_goals FROM matches WHERE season='2526' ORDER BY date DESC LIMIT 5")
for row in cursor.fetchall():
    print(row)
conn.close()
