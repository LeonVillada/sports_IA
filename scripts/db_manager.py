import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

def create_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password=''
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

def setup_database():
    conn = create_connection()
    if not conn: return
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS sports_ai_db")
        cursor.execute("USE sports_ai_db")
        cursor.execute("CREATE TABLE IF NOT EXISTS leagues (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL, country VARCHAR(50), api_id INT UNIQUE)")
        cursor.execute("CREATE TABLE IF NOT EXISTS teams (id INT AUTO_INCREMENT PRIMARY KEY, league_id INT, name VARCHAR(100) NOT NULL, api_id INT UNIQUE, FOREIGN KEY (league_id) REFERENCES leagues(id))")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INT AUTO_INCREMENT PRIMARY KEY, 
                date DATETIME, 
                league_id INT, 
                home_team_id INT, 
                away_team_id INT, 
                home_goals INT DEFAULT NULL, 
                away_goals INT DEFAULT NULL, 
                ht_home_goals INT DEFAULT NULL,
                ht_away_goals INT DEFAULT NULL,
                home_shots INT DEFAULT NULL,
                away_shots INT DEFAULT NULL,
                home_shots_on_target INT DEFAULT NULL,
                away_shots_on_target INT DEFAULT NULL,
                home_corners INT DEFAULT NULL,
                away_corners INT DEFAULT NULL,
                home_fouls INT DEFAULT NULL,
                away_fouls INT DEFAULT NULL,
                home_yellow_cards INT DEFAULT NULL,
                away_yellow_cards INT DEFAULT NULL,
                home_red_cards INT DEFAULT NULL,
                away_red_cards INT DEFAULT NULL,
                status VARCHAR(20) DEFAULT 'scheduled', 
                season VARCHAR(10), 
                api_id INT UNIQUE, 
                FOREIGN KEY (league_id) REFERENCES leagues(id), 
                FOREIGN KEY (home_team_id) REFERENCES teams(id), 
                FOREIGN KEY (away_team_id) REFERENCES teams(id)
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS odds (id INT AUTO_INCREMENT PRIMARY KEY, match_id INT, bookmaker VARCHAR(50), home_win_odds FLOAT, draw_odds FLOAT, away_win_odds FLOAT, handicap_line FLOAT, home_handicap_odds FLOAT, away_handicap_odds FLOAT, FOREIGN KEY (match_id) REFERENCES matches(id))")
        print("Base de datos y tablas creadas exitosamente.")
    except Error as e:
        print(f"Error al crear tablas: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    setup_database()
