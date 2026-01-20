import os
import requests
from datetime import datetime, timedelta

# =============================
# VARIABLES ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
LEAGUE = "eng.1"  # Premier League, changeable

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
# RÉCUPÉRER TOUS LES MATCHS DU JOUR
# =============================
def get_today_matches():
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard"
    res = requests.get(url).json()
    events = res.get("events", [])

    today_utc = datetime.utcnow().date()
    today_matches = []

    for match in events:
        match_date = datetime.strptime(match["date"], "%Y-%m-%dT%H:%MZ").date()
        if match_date == today_utc:
            today_matches.append(match)
    return today_matches

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
    home_stats = stats_list[0]["statistics"] if len(stats_list) > 0 else []
    away_stats = stats_list[1]["statistics"] if len(stats_list) > 1 else []

    # Extraire les stats clés
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

    stats_msg = (
        f"Tirs: {shots_home}-{shots_away} | "
        f"Possession: {possession_home}-{possession_away}% | "
        f"Corners: {corners_home}-{corners_away}"
    )

    return home, away, score_home, score_away, stats_msg

# =============================
# RÉCUPÉRER H2H (5 derniers matchs)
# =============================
def get_h2h(home, away):
    # ESPN ne fournit pas directement H2H via endpoint, donc simplifié : récupère les derniers matchs de la ligue et filtre
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard"
    res = requests.get(url).json()
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
def simple_analysis(home_stats, away_stats):
    try:
        home_poss = float(home_stats.split("Possession: ")[1].split("-")[0].replace("%", ""))
        away_poss = float(home_stats.split("Possession: ")[1].split("-")[0].replace("%", ""))
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
    matches = get_today_matches()
    if not matches:
        send_to_telegram("Aucun match trouvé pour aujourd'hui")
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

        analysis = simple_analysis(stats_msg, stats_msg)
        analyses.append(f"{home} vs {away} -> {analysis}")

    # Analyse finale
    send_to_telegram("📊 Analyse de tous les matchs d'aujourd'hui :\n" + "\n".join(analyses))

if __name__ == "__main__":
    main()
