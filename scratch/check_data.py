import requests
import pandas as pd
from io import StringIO

leagues = ["E0", "SP1", "I1", "D1", "F1"]
season = "2526"

for league in leagues:
    url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
    print(f"Checking {url}")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text))
            print(f"League {league} has {len(df)} matches.")
            if len(df) > 0:
                print(df.tail(2))
        else:
            print(f"Failed to get {league}: {response.status_code}")
    except Exception as e:
        print(f"Error checking {league}: {e}")
