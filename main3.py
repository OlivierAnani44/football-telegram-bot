import os
import requests
from datetime import datetime

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

LEAGUE = "cl"     # Champions League
SEASON = 2025     # Saison (ex: 2024/2025)

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

BASE_URL = "https://api.openligadb.de"

# =========================
# TELEGRAM
# =========================
def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message
    }
    requests.post(url, data=payload, timeout=15)

# =========================
# API OPENLIGADB
# =========================
def fetch_all_matches():
    url = f"{BASE_URL}/getmatchdata/{LEAGUE}/{SEASON}"
    return requests.get(url, timeout=20).json()

def filter_today_matches(matches):
    today = datetime.utcnow().date()
    today_matches = []

    for m in matches:
        match_date = datetime.fromisoformat(
            m["MatchDateTime"].replace("Z", "")
        ).date()

        if match_date == today:
            today_matches.append(m)

    return today_matches

# =========================
# DATA ANALYSIS
# =========================
def get_score(match):
    if match["MatchResults"]:
        result = match["MatchResults"][-1]
        return f'{result["PointsTeam1"]}-{result["PointsTeam2"]}'
    return "Non joué"

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

# =========================
# FORMAT MESSAGE
# =========================
def format_match_message(match, all_matches):
    team1 = match["Team1"]["TeamName"]
    team2 = match["Team2"]["TeamName"]
    score = get_score(match)

    h2h = "\n".join(get_h2h(team1, team2, all_matches))
    form1 = get_form(team1, all_matches)
    form2 = get_form(team2, all_matches)
    prediction = predict_winner(team1, team2, all_matches)

    return f"""
🏆 Ligue des Champions
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

# =========================
# MAIN
# =========================
def main():
    all_matches = fetch_all_matches()
    today_matches = filter_today_matches(all_matches)

    if not today_matches:
        send_to_telegram("❌ Aucun match de Ligue des Champions aujourd’hui.")
        return

    send_to_telegram(f"🏆 Matchs de Ligue des Champions – {datetime.utcnow().date()}")

    for match in today_matches:
        msg = format_match_message(match, all_matches)
        send_to_telegram(msg)

    send_to_telegram("✅ Analyse terminée")

if __name__ == "__main__":
    main()
