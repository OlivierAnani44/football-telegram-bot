import os
import requests
from datetime import datetime

# =============================
# VARIABLES ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
LEAGUE = "eng.1"  # Premier League, modifiable

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
# RÉCUPÉRER LES TOP MATCHS DU JOUR
# =============================
def get_top_matches():
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard?favorites=true"
    headers = {"User-Agent": "ESPN/Android", "Accept": "application/json"}

    res = requests.get(url, headers=headers).json()
    events = res.get("events", [])

    today_utc = datetime.utcnow().date()
    today_matches = []

    for match in events:
        match_date = datetime.strptime(match["date"], "%Y-%m-%dT%H:%MZ").date()
        if match_date == today_utc:
            today_matches.append(match)

    return today_matches

# =============================
# RÉCUPÉRER STATS D’UN MATCH
# =============================
def get_match_stats(gameId):
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/summary?event={gameId}"
    headers = {"User-Agent": "ESPN/Android", "Accept": "application/json"}
    res = requests.get(url, headers=headers).json()

    comp = res.get("header", {}).get("competitions", [])[0]

    home = comp["competitors"][0]["team"]["displayName"]
    away = comp["competitors"][1]["team"]["displayName"]
    score_home = comp["competitors"][0]["score"]
    score_away = comp["competitors"][1]["score"]

    # Boxscore
    stats_list = res.get("boxscore", {}).get("teams", [])
    home_stats = stats_list[0]["statistics"] if len(stats_list) > 0 else []
    away_stats = stats_list[1]["statistics"] if len(stats_list) > 1 else []

    def get_stat(stats, name):
        for s in stats:
            if s.get("name") == name:
                return s.get("value")
        return "-"

    stats_msg = (
        f"Tirs: {get_stat(home_stats,'Shots')}-{get_stat(away_stats,'Shots')} | "
        f"Possession: {get_stat(home_stats,'Possession')}-{get_stat(away_stats,'Possession')}% | "
        f"Corners: {get_stat(home_stats,'Corners')}-{get_stat(away_stats,'Corners')}"
    )

    return home, away, score_home, score_away, stats_msg

# =============================
# RÉCUPÉRER H2H (simplifié 5 derniers matchs)
# =============================
def get_h2h(home, away):
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard"
    headers = {"User-Agent": "ESPN/Android", "Accept": "application/json"}
    res = requests.get(url, headers=headers).json()
    events = res.get("events", [])
    results = []

    for match in events:
        c = match["competitions"][0]
        teams = [c["competitors"][0]["team"]["shortDisplayName"], c["competitors"][1]["team"]["shortDisplayName"]]
        if home in teams and away in teams:
            h = teams[0]
            a = teams[1]
            sh = c["competitors"][0]["score"]
            sa = c["competitors"][1]["score"]
            results.append(f"{h} {sh}-{sa} {a}")
        if len(results) >= 5:
            break
    return results if results else ["Aucun H2H trouvé"]

# =============================
# ANALYSE SIMPLE
# =============================
def simple_analysis(stats_msg):
    try:
        home_poss = float(stats_msg.split("Possession: ")[1].split("-")[0].replace("%",""))
        away_poss = float(stats_msg.split("Possession: ")[1].split("-")[0].replace("%",""))
        if home_poss > away_poss:
            return "Équipe favorite : Home"
        elif away_poss > home_poss:
            return "Équipe favorite : Away"
        else:
            return "Match équilibré"
    except:
        return "Analyse indisponible"

# =============================
# MAIN
# =============================
def main():
    matches = get_top_matches()
    if not matches:
        send_to_telegram("Aucun top match trouvé pour aujourd'hui")
        return

    analyses = []

    for match in matches:
        gameId = match.get("id")
        if not gameId:
            continue

        home, away, sh, sa, stats_msg = get_match_stats(gameId)
        send_to_telegram(f"⚽ {home} vs {away}\nScore: {sh}-{sa}\n{stats_msg}")

        h2h_results = get_h2h(home, away)
        send_to_telegram("H2H :\n" + "\n".join(h2h_results))

        analysis = simple_analysis(stats_msg)
        analyses.append(f"{home} vs {away} -> {analysis}")

    send_to_telegram("📊 Analyse de tous les top matchs du jour :\n" + "\n".join(analyses))

if __name__ == "__main__":
    main()
