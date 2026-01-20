import os
import requests
from datetime import datetime

# =============================
# CONFIGURATION
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
SEASON = 2025  # Saison exemple

BASE_URL = "https://api.openligadb.de"

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =============================
# TELEGRAM
# =============================
def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": message}
    requests.post(url, data=payload, timeout=15)

# =============================
# RÉCUPÉRER toutes les ligues
# =============================
def fetch_all_leagues():
    url = f"{BASE_URL}/getavailableleagues"
    return requests.get(url, timeout=20).json()

# =============================
# RÉCUPÉRER les matchs d’une ligue
# =============================
def fetch_all_matches(league_shortcut):
    url = f"{BASE_URL}/getmatchdata/{league_shortcut}/{SEASON}"
    return requests.get(url, timeout=20).json()

# =============================
# SCORE
# =============================
def get_score(match):
    if match["MatchResults"]:
        result = match["MatchResults"][-1]
        return f'{result["PointsTeam1"]}-{result["PointsTeam2"]}'
    return "Non joué"

# =============================
# H2H
# =============================
def get_h2h(team1, team2, all_matches, limit=5):
    h2h = []
    for m in reversed(all_matches):
        t1 = m["Team1"]["TeamName"]
        t2 = m["Team2"]["TeamName"]
        if {t1, t2} == {team1, team2} and m["MatchResults"]:
            r = m["MatchResults"][-1]
            h2h.append(f"{t1} {r['PointsTeam1']}-{r['PointsTeam2']} {t2}")
            if len(h2h) >= limit:
                break
    return h2h if h2h else ["Aucun historique"]

# =============================
# Forme récente
# =============================
def get_form(team, all_matches, limit=5):
    form = []
    for m in reversed(all_matches):
        if m["MatchResults"]:
            t1 = m["Team1"]["TeamName"]
            t2 = m["Team2"]["TeamName"]
            r = m["MatchResults"][-1]
            if team == t1:
                form.append("V" if r["PointsTeam1"] > r["PointsTeam2"]
                            else "N" if r["PointsTeam1"] == r["PointsTeam2"] else "D")
            elif team == t2:
                form.append("V" if r["PointsTeam2"] > r["PointsTeam1"]
                            else "N" if r["PointsTeam1"] == r["PointsTeam2"] else "D")
            if len(form) >= limit:
                break
    return " ".join(form) if form else "N/A"

# =============================
# Analyse simple
# =============================
def predict_winner(team1, team2, all_matches):
    f1 = get_form(team1, all_matches)
    f2 = get_form(team2, all_matches)
    score1 = f1.count("V")
    score2 = f2.count("V")
    if score1 > score2:
        return f"Avantage : {team1}"
    elif score2 > score1:
        return f"Avantage : {team2}"
    return "Match équilibré"

# =============================
# Formater message Telegram
# =============================
def format_match_message(match, all_matches, league_name):
    team1 = match["Team1"]["TeamName"]
    team2 = match["Team2"]["TeamName"]
    score = get_score(match)
    h2h = "\n".join(get_h2h(team1, team2, all_matches))
    form1 = get_form(team1, all_matches)
    form2 = get_form(team2, all_matches)
    prediction = predict_winner(team1, team2, all_matches)

    return f"""
🏆 {league_name}
⚽ {team1} vs {team2}
📊 Score : {score}

🔁 H2H :
{h2h}

📈 Forme récente :
{team1} : {form1}
{team2} : {form2}

🔮 Analyse :
{prediction}
""".strip()

# =============================
# MAIN
# =============================
def main():
    leagues = fetch_all_leagues()

    for league in leagues:
        league_name = league["LeagueName"]
        league_shortcut = league["LeagueShortcut"]

        try:
            all_matches = fetch_all_matches(league_shortcut)
            if not all_matches:
                continue

            send_to_telegram(f"🏆 {league_name} – Saison {SEASON}")

            for match in all_matches:
                msg = format_match_message(match, all_matches, league_name)
                send_to_telegram(msg)

        except Exception as e:
            send_to_telegram(f"❌ Erreur récupération {league_name} : {e}")

    send_to_telegram("✅ Analyse terminée pour toutes les ligues.")

if __name__ == "__main__":
    main()
