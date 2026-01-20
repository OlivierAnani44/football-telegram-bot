import os
import requests
from datetime import datetime

# =============================
# VARIABLES ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

LEAGUE = "cl"  # Ligue des Champions
YEAR = 2026    # saison actuelle

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =============================
# FONCTION TELEGRAM
# =============================
def send_to_telegram(msg: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload)

# =============================
# RÉCUPÉRER TOUS LES MATCHS DE LA SAISON
# =============================
def get_all_matches():
    url = f"https://api.openligadb.de/getmatchdata/{LEAGUE}/{YEAR}"
    res = requests.get(url).json()
    return res

# =============================
# FILTRER LES MATCHS D’AUJOURD’HUI
# =============================
def get_today_matches(all_matches):
    today = datetime.utcnow().date()
    today_matches = []
    for m in all_matches:
        match_date = datetime.fromisoformat(m["MatchDateTime"][:-1]).date()  # retirer Z
        if match_date == today:
            today_matches.append(m)
    return today_matches

# =============================
# RÉCUPÉRER SCORE ET STATISTIQUES
# =============================
def get_match_info(match):
    team1 = match["Team1"]["TeamName"]
    team2 = match["Team2"]["TeamName"]
    score = "Non joué"
    if match.get("MatchResults"):
        score = f"{match['MatchResults'][0]['PointsTeam1']}-{match['MatchResults'][0]['PointsTeam2']}"
    return team1, team2, score

# =============================
# MAIN
# =============================
def main():
    all_matches = get_all_matches()
    today_matches = get_today_matches(all_matches)

    if not today_matches:
        send_to_telegram("Aucun match de Ligue des Champions prévu pour aujourd'hui.")
        return

    for m in today_matches:
        team1, team2, score = get_match_info(m)
        send_to_telegram(f"⚽ {team1} vs {team2}\nScore: {score}")

if __name__ == "__main__":
    main()
