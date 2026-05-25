import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'data', 'system_config.json')

DEFAULT_CONFIG = {
    "last_sync_date": "2024-01-01",  # A fallback date far in the past
    "last_sync_time_str": "No sincronizado",
    "last_accuracy": 0,
    "season_active": True,           # False cuando no hay fixtures futuros (fin de temporada)
    "sync_message": ""               # Último mensaje del proceso de sincronización
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        # Create data dir if not exists
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("WARN: system_config.json is corrupted. Using defaults.")
        return DEFAULT_CONFIG

def save_config(config_data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config_data, f, indent=4)

def update_config(key, value):
    config = load_config()
    config[key] = value
    save_config(config)
