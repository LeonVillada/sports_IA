import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scripts.config import update_config
from datetime import datetime

# Set the last sync date to yesterday to test incremental sync
update_config("last_sync_date", "2026-05-14")
print("Config updated to 2026-05-14")
