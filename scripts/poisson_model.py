import pandas as pd
import numpy as np
from scipy.stats import poisson
from scripts.db_manager import create_connection

def calculate_team_strengths(limit_matches=20):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    # Cargar los partidos más recientes para mayor relevancia (Fase 2)
    cursor.execute(f"""
        SELECT home_team_id, away_team_id, home_goals, away_goals 
        FROM matches 
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY date DESC LIMIT {limit_matches * 50}
    """)
    matches = cursor.fetchall()
    conn.close()
    
    if not matches:
        return None

    df = pd.DataFrame(matches)
    
    avg_home_goals = df['home_goals'].mean()
    avg_away_goals = df['away_goals'].mean()
    
    home_attack = df.groupby('home_team_id')['home_goals'].mean() / avg_home_goals
    away_defense = df.groupby('home_team_id')['away_goals'].mean() / avg_away_goals
    
    away_attack = df.groupby('away_team_id')['away_goals'].mean() / avg_away_goals
    home_defense = df.groupby('away_team_id')['home_goals'].mean() / avg_home_goals
    
    return {
        "avg_home": avg_home_goals, "avg_away": avg_away_goals,
        "home_attack": home_attack, "home_defense": home_defense,
        "away_attack": away_attack, "away_defense": away_defense
    }

def predict_match(home_id, away_id, strengths):
    if not strengths: return None
    
    l_home = strengths['home_attack'].get(home_id, 1) * strengths['away_defense'].get(away_id, 1) * strengths['avg_home']
    l_away = strengths['away_attack'].get(away_id, 1) * strengths['home_defense'].get(home_id, 1) * strengths['avg_away']
    
    # Matriz de probabilidad (0 a 6 goles)
    max_g = 7
    prob_matrix = np.outer(poisson.pmf(range(max_g), l_home), poisson.pmf(range(max_g), l_away))
    
    prob_home = np.sum(np.tril(prob_matrix, -1))
    prob_draw = np.sum(np.diag(prob_matrix))
    prob_away = np.sum(np.triu(prob_matrix, 1))
    
    # Hándicap Asiático Simple (Basado en la diferencia de goles esperada)
    # Si la diferencia es > 0.5, sugerimos Local -0.5
    diff = l_home - l_away
    ah_suggestion = "0.0"
    if diff > 0.75: ah_suggestion = "-1.0"
    elif diff > 0.4: ah_suggestion = "-0.5"
    elif diff < -0.75: ah_suggestion = "+1.0"
    elif diff < -0.4: ah_suggestion = "+0.5"

    return {
        "home_win": float(round(prob_home * 100, 1)),
        "draw": float(round(prob_draw * 100, 1)),
        "away_win": float(round(prob_away * 100, 1)),
        "expected_score": f"{round(l_home,1)} - {round(l_away,1)}",
        "ah_suggestion": ah_suggestion,
        "total_expected": float(round(l_home + l_away, 2)),
        "advice": get_betting_advice(prob_home, prob_away, prob_draw, ah_suggestion)
    }

def get_betting_advice(p_home, p_away, p_draw, ah):
    """Convierte porcentajes en instrucciones claras de apuesta"""
    if p_home > 0.65:
        return {"type": "Victoria Directa", "label": "Local Fuerte", "color": "#10b981", "stake": 3}
    if p_away > 0.65:
        return {"type": "Victoria Directa", "label": "Visitante Fuerte", "color": "#f87171", "stake": 3}
    
    if ah == "-0.5":
        return {"type": "Hándicap", "label": "Local -0.5 (Ganar)", "color": "#38bdf8", "stake": 2}
    if ah == "+0.5":
        return {"type": "Hándicap", "label": "Doble Oportunidad X2", "color": "#fbbf24", "stake": 2}
    
    if p_draw > 0.35:
        return {"type": "Riesgo", "label": "Posible Empate", "color": "#94a3b8", "stake": 1}
        
    return {"type": "Neutral", "label": "No apostar (Poco valor)", "color": "#475569", "stake": 0}

if __name__ == "__main__":
    strengths = calculate_team_strengths()
    print("Modelo de Poisson inicializado.")
