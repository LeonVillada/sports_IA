import os
import sys
import json
import numpy as np
from scripts.db_manager import create_connection

# Asegurar que reconozca los scripts de lógica
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

WEIGHTS_FILE = os.path.join(BASE_DIR, "data", "model_weights.json")

def train_adjustment_factors(silent=False):
    """Analiza los aciertos/fallos para ajustar las probabilidades del modelo"""
    conn = create_connection()
    if not conn: return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE sports_ai_db")
    
    # Obtener rendimiento por mercado y por rangos de confianza
    cursor.execute("""
        SELECT market, 
               FLOOR(confidence/10)*10 as conf_bracket,
               AVG(is_hit) as hit_rate,
               COUNT(*) as total
        FROM predictions
        WHERE is_hit IS NOT NULL
        GROUP BY market, conf_bracket
    """)
    performance = cursor.fetchall()
    
    # Crear un mapeo de ajustes
    adjustments = {}
    for p in performance:
        mkt = p['market']
        bracket = int(p['conf_bracket'])
        
        if mkt not in adjustments:
            adjustments[mkt] = {}
            
        # Si la precisión real es menor a la confianza esperada, bajamos la confianza reportada
        # Si es mayor, la subimos.
        expected = bracket + 5 # Punto medio del rango
        actual = p['hit_rate'] * 100
        
        # Factor de ajuste: ratio entre realidad y expectativa
        factor = float(actual / expected) if expected > 0 else 1.0
        adjustments[mkt][bracket] = round(factor, 3)

    # Guardar ajustes
    os.makedirs(os.path.dirname(WEIGHTS_FILE), exist_ok=True)
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(adjustments, f, indent=4)
        
    if not silent: print(f"Factores de ajuste actualizados en {WEIGHTS_FILE}")
    conn.close()
    return adjustments

def get_adjusted_confidence(market, confidence):
    """Aplica los factores aprendidos a una confianza cruda"""
    if not os.path.exists(WEIGHTS_FILE):
        return confidence
        
    try:
        with open(WEIGHTS_FILE, 'r') as f:
            adjustments = json.load(f)
            
        mkt_adj = adjustments.get(market, {})
        bracket = str(int(confidence // 10) * 10)
        
        factor = mkt_adj.get(bracket, 1.0)
        return min(100, round(confidence * factor, 1))
    except:
        return confidence

if __name__ == "__main__":
    train_adjustment_factors()
