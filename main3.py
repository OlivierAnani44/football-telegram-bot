import os
import requests
from datetime import datetime, timedelta

# =============================
# VARIABLES ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
LEAGUE = "eng.1"  # Premier League

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
# RÉCUPÉRER LES MATCHS D’UNE DATE
# =============================
def get_matches_by_date(date_str):
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard?dates={date_str}"
    res = requests.get(url).json()
    return res.get("events", [])

# =============================
# RÉCUPÉRER LES STATS D’UN MATCH
# =============================
def get_match_stats(gameId):
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/summary?event={gameId}"
    res = requests.get(url).json()
    comp = res.get("header", {}).get("competitions", [])[0]
    home = comp["competitors"][0]["team"]["displayName"]
    away = comp["competitors"][1]["team"]["displayName"]
    score_home = comp["competitors"][0]["score"]
    score_away = comp["competitors"][1]["score"]

    # Boxscore stats
    stats_list = res.get("boxscore", {}).get("teams", [])
    home_stats = stats_list[0]["statistics"] if len(stats_list) > 0 else {}
    away_stats = stats_list[1]["statistics"] if len(stats_list) > 1 else {}

    # Extraire certaines stats clés
    def get_stat(stats, name):
        for s in stats:
            if s.get("name") == name:
                return s.get("value")
        return "-"

    shots_home = get_stat(home_stats, "Shots")
    shots_away = get_stat(away_stats, "Shots")
    possession_home = get_stat(home_stats, "Possession")
    possession_away = get_stat(away_stats, "Possession")
    corners_home = get_stat(home_stats, "Corners")
    corners_away = get_stat(away_stats, "Corners")

    msg = (
        f"⚽ <b>{home} vs {away}</b>\n"
        f"Score: {score_home}-{score_away}\n"
        f"Tirs: {shots_home}-{shots_away} | Possession: {possession_home}-{possession_away}% | Corners: {corners_home}-{corners_away}"
    )
    send_to_telegram(msg)

# =============================
# MAIN
# =============================
def main():
    # Date de demain
    tomorrow = datetime.utcnow() + timedelta(days=1)
    date_str = tomorrow.strftime("%Y%m%d")

    matches = get_matches_by_date(date_str)
    if not matches:
        send_to_telegram(f"Aucun match trouvé pour demain ({date_str})")
        return

    for match in matches:
        gameId = match.get("id")
        if gameId:
            get_match_stats(gameId)

if __name__ == "__main__":
    main()
