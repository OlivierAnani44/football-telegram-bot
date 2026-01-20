import requests
from datetime import datetime

LEAGUES = [
    "eng.1", "esp.1", "ita.1", "ger.1", "fra.1",
    "por.1", "ned.1", "uefa.champions"
]

def fetch_today_matches():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    all_matches = []

    for league in LEAGUES:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"[WARN] Impossible de récupérer {league}")
            continue

        data = resp.json()
        events = data.get("events", [])
        for e in events:
            if e.get("status", {}).get("type", {}).get("completed") is False:  # Match pas encore fini
                all_matches.append(e)

    return all_matches
