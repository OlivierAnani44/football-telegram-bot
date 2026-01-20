import os
import requests
from datetime import datetime

# =============================
# VARIABLES ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

LEAGUE = "cl"      # Ligue des Champions
YEAR = 2026         # Saison actuelle
TOP_TEAMS = [       # Équipes “populaires” de la Champions League
    "Real Madrid", "Barcelona", "Manchester City", "Liverpool",
    "Bayern München", "Paris Saint-Germain", "Chelsea", "Juventus"
]

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
# RÉCUPÉRER LES MATCHS D’UNE JOURNÉE
# =============================
def get_matchday_matches():
    url = f"https://api.openligadb.de/getmatchdata/{LEAGUE}/{YEAR}"
    res = requests.get(url).json()
    return res

# =============================
# FILTRER LES TOP MATCHS DU JOUR
# =============================
def filter_today_top_matches(matches):
    today = datetime.utcnow().date()
    top_matches = []
    for m in matches:
        match_date = datetime.fromisoformat(m["MatchDateTime"][:-1]).date()  # retirer Z
        team1 = m["Team1"]["TeamName"]
        team2 = m["Team2"]["TeamName"]

        if match_date == today and (team1 in TOP_TEAMS or team2 in TOP_TEAMS):
            top_matches.append(m)
    return top_matches

# =============================
# H2H : 5 derniers matchs entre les équipes
# =============================
def get_h2h(team1, team2, all_matches):
    h2h = []
    for m in reversed(all_matches):  # du plus récent au plus ancien
        t1 = m["Team1"]["TeamName"]
        t2 = m["Team2"]["TeamName"]
        if {t1, t2} == {team1, team2}:
            score = f"{m['MatchResults'][0]['PointsTeam1']}-{m['MatchResults'][0]['PointsTeam2']}" \
                    if m.get("MatchResults") else "Non joué"
            h2h.append(f"{t1} {score} {t2}")
            if len(h2h) >= 5:
                break
    return h2h if h2h else ["Aucun H2H trouvé"]

# =============================
# FORME RÉCENTE : derniers 5 matchs d’une équipe
# =============================
def get_form(team, all_matches):
    form = []
    for m in reversed(all_matches):
        if m["Team1"]["TeamName"] == team or m["Team2"]["TeamName"] == team:
            score1 = m['MatchResults'][0]['PointsTeam1']
            score2 = m['MatchResults'][0]['PointsTeam2']
            if (m["Team1"]["TeamName"] == team and score1 > score2) or (m["Team2"]["TeamName"] == team and score2 > score1):
                form.append("V")
            elif score1 == score2:
                form.append("N")
            else:
                form.append("D")
            if len(form) >= 5:
                break
    return form if form else ["N/A"]

# =============================
# ANALYSE SIMPLE
# =============================
def analyze_match(team1, team2, all_matches):
    form1 = get_form(team1, all_matches)
    form2 = get_form(team2, all_matches)
    score1 = form1.count("V")
    score2 = form2.count("V")
    if score1 > score2:
        return f"Équipe favorite : {team1}"
    elif score2 > score1:
        return f"Équipe favorite : {team2}"
    else:
        return "Match équilibré"

# =============================
# MAIN
# =============================
def main():
    all_matches = get_matchday_matches()
    top_matches = filter_today_top_matches(all_matches)

    if not top_matches:
        send_to_telegram("Aucun top match de Ligue des Champions pour aujourd'hui.")
        return

    analyses = []

    for m in top_matches:
        team1 = m["Team1"]["TeamName"]
        team2 = m["Team2"]["TeamName"]
        score = f"{m['MatchResults'][0]['PointsTeam1']}-{m['MatchResults'][0]['PointsTeam2']}" \
                if m.get("MatchResults") else "Non joué"

        send_to_telegram(f"⚽ {team1} vs {team2}\nScore: {score}")

        h2h_results = get_h2h(team1, team2, all_matches)
        send_to_telegram("H2H (5 derniers matchs) :\n" + "\n".join(h2h_results))

        analysis = analyze_match(team1, team2, all_matches)
        analyses.append(f"{team1} vs {team2} -> {analysis}")

    send_to_telegram("📊 Analyse finale des top matchs de Ligue des Champions :\n" + "\n".join(analyses))

if __name__ == "__main__":
    main()
