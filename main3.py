import os
import requests
from datetime import datetime

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
# RÉCUPÉRER LES MATCHS D'AUJOURD'HUI
# =============================
def get_matches_today():
    today_str = datetime.utcnow().strftime("%Y%m%d")
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard?dates={today_str}"
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
    home_stats = stats_list[0]["statistics"] if len(stats_list) > 0 else []
    away_stats = stats_list[1]["statistics"] if len(stats_list) > 1 else []

    def get_stat(stats, name):
        for s in stats:
            if s.get("name") == name:
                return s.get("value")
        return "-"

    stats_msg = (
        f"Tirs: {get_stat(home_stats, 'Shots')}-{get_stat(away_stats, 'Shots')}\n"
        f"Possession: {get_stat(home_stats, 'Possession')}-{get_stat(away_stats, 'Possession')}%\n"
        f"Corners: {get_stat(home_stats, 'Corners')}-{get_stat(away_stats, 'Corners')}"
    )

    return home, away, score_home, score_away, stats_msg

# =============================
# SIMPLIFIED H2H (dernier match entre les deux équipes)
# =============================
def get_h2h(home, away):
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard?h2h={home},{away}"
    try:
        res = requests.get(url).json()
        events = res.get("events", [])
        results = []
        for match in events[:5]:  # max 5 derniers H2H
            c = match["competitions"][0]
            h = c["competitors"][0]["team"]["shortDisplayName"]
            a = c["competitors"][1]["team"]["shortDisplayName"]
            sh = c["competitors"][0]["score"]
            sa = c["competitors"][1]["score"]
            results.append(f"{h} {sh}-{sa} {a}")
        return results if results else ["Aucun H2H trouvé"]
    except:
        return ["Erreur récupération H2H"]

# =============================
# ANALYSE SIMPLE
# =============================
def simple_analysis(home_stats, away_stats):
    # Ici, analyse simplifiée : plus de tirs + possession + derniers résultats
    # Pour l'exemple, juste on compare possession
    try:
        home_poss = float(home_stats.split("Possession: ")[1].split("-")[0].replace("%", ""))
        away_poss = float(away_stats.split("Possession: ")[1].split("-")[0].replace("%", ""))
        if home_poss > away_poss:
            return "Équipe favorite : " + home_stats.split("\n")[0].split(": ")[1].split("-")[0]
        elif away_poss > home_poss:
            return "Équipe favorite : " + away_stats.split("\n")[0].split(": ")[1].split("-")[0]
        else:
            return "Match équilibré"
    except:
        return "Analyse indisponible"

# =============================
# MAIN
# =============================
def main():
    matches = get_matches_today()
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
        send_to_telegram(f"H2H :\n" + "\n".join(h2h_results))

        analysis = simple_analysis(stats_msg, stats_msg)
        analyses.append(f"{home} vs {away} -> {analysis}")

    # Envoi analyse finale
    send_to_telegram("📊 Analyse de tous les matchs d'aujourd'hui :\n" + "\n".join(analyses))

if __name__ == "__main__":
    main()
