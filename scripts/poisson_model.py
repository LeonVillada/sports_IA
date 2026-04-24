import pandas as pd
import numpy as np
from scipy.stats import poisson
from scripts.db_manager import create_connection

def calculate_team_strengths():
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    # Cargar todos los partidos finalizados
    cursor.execute("""
        SELECT home_team_id, away_team_id, home_goals, away_goals 
        FROM matches 
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
    """)
    matches = cursor.fetchall()
    conn.close()
    
    if not matches:
        return None

    df = pd.DataFrame(matches)
    
    # Calcular promedios de la liga
    avg_home_goals = df['home_goals'].mean()
    avg_away_goals = df['away_goals'].mean()
    
    # Calcular fuerza de ataque y defensa por equipo
    home_attack = df.groupby('home_team_id')['home_goals'].mean() / avg_home_goals
    away_defense = df.groupby('home_team_id')['away_goals'].mean() / avg_away_goals
    
    away_attack = df.groupby('away_team_id')['away_goals'].mean() / avg_away_goals
    home_defense = df.groupby('away_team_id')['home_goals'].mean() / avg_home_goals
    
    return {
        "avg_home": avg_home_goals,
        "avg_away": avg_away_goals,
        "home_attack": home_attack,
        "home_defense": home_defense,
        "away_attack": away_attack,
        "away_defense": away_defense
    }

def predict_match(home_id, away_id, strengths):
    if not strengths: return None
    
    # λ (Lambda) para el equipo local = AtaqueLocal * DefensaVisitante * PromedioGolesLocal
    lambda_home = strengths['home_attack'].get(home_id, 1) * \
                  strengths['away_defense'].get(away_id, 1) * \
                  strengths['avg_home']
                  
    # λ (Lambda) para el equipo visitante = AtaqueVisitante * DefensaLocal * PromedioGolesVisitante
    lambda_away = strengths['away_attack'].get(away_id, 1) * \
                  strengths['home_defense'].get(home_id, 1) * \
                  strengths['avg_away']
    
    # Calcular matriz de probabilidades (hasta 5 goles)
    prob_matrix = np.outer(poisson.pmf(range(6), lambda_home), poisson.pmf(range(6), lambda_away))
    
    prob_home_win = np.sum(np.tril(prob_matrix, -1))
    prob_draw = np.sum(np.diag(prob_matrix))
    prob_away_win = np.sum(np.triu(prob_matrix, 1))
    
    return {
        "home_win": round(prob_home_win * 100, 2),
        "draw": round(prob_draw * 100, 2),
        "away_win": round(prob_away_win * 100, 2),
        "expected_score": f"{round(lambda_home,1)} - {round(lambda_away,1)}"
    }

if __name__ == "__main__":
    strengths = calculate_team_strengths()
    print("Modelo de Poisson inicializado.")
