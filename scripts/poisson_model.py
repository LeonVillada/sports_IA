import pandas as pd
import numpy as np
from scipy.stats import poisson
from scripts.db_manager import create_connection

def calculate_team_strengths(limit_matches=20):
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    # Cargar los partidos más recientes con estadísticas completas
    cursor.execute(f"""
        SELECT home_team_id, away_team_id, home_goals, away_goals, 
               home_corners, away_corners, home_yellow_cards, away_yellow_cards
        FROM matches 
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY date DESC LIMIT {limit_matches * 50}
    """)
    matches = cursor.fetchall()
    conn.close()
    
    if not matches:
        return None

    df = pd.DataFrame(matches)
    
    # Goles
    avg_home_goals = df['home_goals'].mean()
    avg_away_goals = df['away_goals'].mean()
    home_attack = df.groupby('home_team_id')['home_goals'].mean() / avg_home_goals
    away_defense = df.groupby('home_team_id')['away_goals'].mean() / avg_away_goals
    away_attack = df.groupby('away_team_id')['away_goals'].mean() / avg_away_goals
    home_defense = df.groupby('away_team_id')['home_goals'].mean() / avg_home_goals

    # Córners (Promedios directos por ahora para simplicidad)
    home_corners_avg = df.groupby('home_team_id')['home_corners'].mean()
    away_corners_avg = df.groupby('away_team_id')['away_corners'].mean()
    
    # Tarjetas (Promedios directos)
    home_cards_avg = df.groupby('home_team_id')['home_yellow_cards'].mean()
    away_cards_avg = df.groupby('away_team_id')['away_yellow_cards'].mean()
    
    return {
        "avg_home": avg_home_goals, "avg_away": avg_away_goals,
        "home_attack": home_attack, "home_defense": home_defense,
        "away_attack": away_attack, "away_defense": away_defense,
        "home_corners": home_corners_avg, "away_corners": away_corners_avg,
        "home_cards": home_cards_avg, "away_cards": away_cards_avg,
        "global_avg_corners": (df['home_corners'].mean() + df['away_corners'].mean()),
        "global_avg_cards": (df['home_yellow_cards'].mean() + df['away_yellow_cards'].mean())
    }

def predict_match(home_id, away_id, strengths):
    if not strengths: return None
    
    # Esperanzas de gol
    l_home = strengths['home_attack'].get(home_id, 1) * strengths['away_defense'].get(away_id, 1) * strengths['avg_home']
    l_away = strengths['away_attack'].get(away_id, 1) * strengths['home_defense'].get(home_id, 1) * strengths['avg_away']
    
    # Matriz de probabilidad (0 a 7 goles para mayor precisión)
    max_g = 8
    prob_matrix = np.outer(poisson.pmf(range(max_g), l_home), poisson.pmf(range(max_g), l_away))
    
    # Probabilidades 1X2
    prob_home = np.sum(np.tril(prob_matrix, -1))
    prob_draw = np.sum(np.diag(prob_matrix))
    prob_away = np.sum(np.triu(prob_matrix, 1))
    
    # Probabilidad Over 2.5
    prob_over_2_5 = 1 - (prob_matrix[0,0] + prob_matrix[0,1] + prob_matrix[0,2] + 
                         prob_matrix[1,0] + prob_matrix[1,1] + prob_matrix[2,0])
    
    # Probabilidad Ambos Marcan (BTTS)
    # 1 - (P(0-0) + P(X-0) + P(0-X))
    prob_no_btts = prob_matrix[0,0] + np.sum(prob_matrix[1:, 0]) + np.sum(prob_matrix[0, 1:])
    prob_btts = 1 - prob_no_btts

    # Córners y Tarjetas (Modelo simplificado de promedios cruzados)
    exp_corners = (strengths['home_corners'].get(home_id, 5) + strengths['away_corners'].get(away_id, 5))
    exp_cards = (strengths['home_cards'].get(home_id, 2) + strengths['away_cards'].get(away_id, 2))
    
    # Hándicap Asiático
    diff = l_home - l_away
    ah_suggestion = "0.0"
    if diff > 0.75: ah_suggestion = "-1.0"
    elif diff > 0.4: ah_suggestion = "-0.5"
    elif diff < -0.75: ah_suggestion = "+1.0"
    elif diff < -0.4: ah_suggestion = "+0.5"

    predictions = {
        "home_win": float(round(prob_home * 100, 1)),
        "draw": float(round(prob_draw * 100, 1)),
        "away_win": float(round(prob_away * 100, 1)),
        "over_2_5": float(round(prob_over_2_5 * 100, 1)),
        "btts": float(round(prob_btts * 100, 1)),
        "exp_corners": round(exp_corners, 1),
        "exp_cards": round(exp_cards, 1),
        "expected_score": f"{round(l_home,1)} - {round(l_away,1)}",
        "ah_suggestion": ah_suggestion,
    }
    
    predictions["advice"] = get_betting_advice(predictions)
    return predictions

def get_betting_advice(p):
    """Genera múltiples sugerencias basadas en diferentes mercados"""
    advices = []
    
    # Sugerencia de Resultado
    if p['home_win'] > 70:
        advices.append({"market": "1X2", "label": "Local Fuerte", "conf": p['home_win'], "color": "#10b981"})
    elif p['away_win'] > 70:
        advices.append({"market": "1X2", "label": "Visitante Fuerte", "conf": p['away_win'], "color": "#f87171"})
    
    # Sugerencia de Goles
    if p['over_2_5'] > 65:
        advices.append({"market": "Goles", "label": "Over 2.5 Goles", "conf": p['over_2_5'], "color": "#38bdf8"})
    elif p['over_2_5'] < 35:
        advices.append({"market": "Goles", "label": "Under 2.5 Goles", "conf": 100 - p['over_2_5'], "color": "#94a3b8"})
        
    # Sugerencia Ambos Marcan
    if p['btts'] > 65:
        advices.append({"market": "BTTS", "label": "Ambos Marcan: SÍ", "conf": p['btts'], "color": "#fbbf24"})

    # Sugerencia de Córners
    if p['exp_corners'] > 10.5:
        advices.append({"market": "Córners", "label": "Más de 9.5 Córners", "conf": 75, "color": "#818cf8"})

    # Ordenar por confianza
    advices = sorted(advices, key=lambda x: x['conf'], reverse=True)
    return advices[0] if advices else {"market": "General", "label": "Poco valor", "conf": 0, "color": "#475569"}

if __name__ == "__main__":
    strengths = calculate_team_strengths()
    print("Modelo de Poisson inicializado.")
