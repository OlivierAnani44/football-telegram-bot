import requests

API_KEY = "API_FOOTBALL_KEY"
URL = "https://v3.football.api-sports.io/fixtures?live=all"
HEADERS = {"x-apisports-key": API_KEY}

known_reds = set()

def check_red_cards():
    r = requests.get(URL, headers=HEADERS)
    matches = r.json()["response"]

    alerts = []

    for m in matches:
        fixture_id = m["fixture"]["id"]
        league = m["league"]["name"]
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        for event in m["events"]:
            if event["type"] == "Card" and event["detail"] == "Red Card":
                key = f"{fixture_id}-{event['player']['name']}"
                if key not in known_reds:
                    known_reds.add(key)

                    alerts.append(
                        f"""🟥 **CARTON ROUGE !**

⚽ {home} 🆚 {away}
👤 Joueur : {event['player']['name']}
⏱ {event['time']['elapsed']}'
🏆 {league}

🔥 Match totalement relancé !
"""
                    )

    return alerts
