from scripts.db_manager import create_connection

def migrate_db():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor()
    cursor.execute("USE sports_ai_db")
    
    new_columns = [
        ("ht_home_goals", "INT DEFAULT NULL"),
        ("ht_away_goals", "INT DEFAULT NULL"),
        ("home_shots", "INT DEFAULT NULL"),
        ("away_shots", "INT DEFAULT NULL"),
        ("home_shots_on_target", "INT DEFAULT NULL"),
        ("away_shots_on_target", "INT DEFAULT NULL"),
        ("home_corners", "INT DEFAULT NULL"),
        ("away_corners", "INT DEFAULT NULL"),
        ("home_fouls", "INT DEFAULT NULL"),
        ("away_fouls", "INT DEFAULT NULL"),
        ("home_yellow_cards", "INT DEFAULT NULL"),
        ("away_yellow_cards", "INT DEFAULT NULL"),
        ("home_red_cards", "INT DEFAULT NULL"),
        ("away_red_cards", "INT DEFAULT NULL")
    ]
    
    # Check existing columns
    cursor.execute("DESCRIBE matches")
    existing = [row[0] for row in cursor.fetchall()]
    
    for col_name, col_type in new_columns:
        if col_name not in existing:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE matches ADD COLUMN {col_name} {col_type}")
    
    conn.commit()
    conn.close()
    print("Migration finished.")

if __name__ == "__main__":
    migrate_db()
