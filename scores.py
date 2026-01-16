import requests

API_KEY = "API_FOOTBALL_KEY"
URL = "https://v3.football.api-sports.io/fixtures?date="

HEADERS = {"x-apisports-key": API_KEY}

def get_today_matches():
    from datetime import date
    today = date.today()

    r = requests.get(URL + str(today), headers=HEADERS)
    data = r.json()

    if not data["response"]:
        return None

    text = "📅 **MATCHS DU JOUR**\n\n"

    for match in data["response"][:8]:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        score = match["goals"]["home"], match["goals"]["away"]
        league = match["league"]["name"]

        text += f"🏟 {home} {score[0]} - {score[1]} {away}\n{league}\n\n"

    return text
