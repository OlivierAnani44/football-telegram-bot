import requests
import time

API_KEY = "API_FOOTBALL_KEY"
URL = "https://v3.football.api-sports.io/fixtures?live=all"
HEADERS = {"x-apisports-key": API_KEY}

last_scores = {}

def check_live_goals():
    r = requests.get(URL, headers=HEADERS)
    data = r.json()["response"]

    alerts = []

    for match in data:
        fixture_id = match["fixture"]["id"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        score = f'{match["goals"]["home"]}-{match["goals"]["away"]}'

        if fixture_id in last_scores and last_scores[fixture_id] != score:
            alerts.append(
                f"🚨 **BUT !!!**\n⚽ {home} {score} {away}\n🔥 Match en direct"
            )

        last_scores[fixture_id] = score

    return alerts
