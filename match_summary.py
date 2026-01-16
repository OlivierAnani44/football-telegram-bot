import requests

API_KEY = "API_FOOTBALL_KEY"
HEADERS = {"x-apisports-key": API_KEY}

URL_FINISHED = "https://v3.football.api-sports.io/fixtures?status=FT"

posted_summaries = set()

def generate_summary(match):
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    score_h = match["goals"]["home"]
    score_a = match["goals"]["away"]
    league = match["league"]["name"]

    goals = [
        e for e in match["events"]
        if e["type"] == "Goal"
    ]

    summary = f"""📝 **RÉSUMÉ DU MATCH**

⚽ {home} {score_h} - {score_a} {away}
🏆 {league}

"""

    for g in goals:
        summary += f"⚽ {g['player']['name']} ({g['time']['elapsed']}')\n"

    summary += "\n🔥 Un match intense jusqu’au coup de sifflet final !"

    return summary

def fetch_finished_matches():
    r = requests.get(URL_FINISHED, headers=HEADERS)
    return r.json()["response"]
