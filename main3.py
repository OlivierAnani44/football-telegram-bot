import os
import requests
from datetime import datetime

# =============================
# CONFIGURATION
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
SEASON = 2025  # Saison exemple OpenLigaDB

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =============================
# TELEGRAM
# =============================
def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=payload, timeout=15)

# =============================
# OPENLIGADB - LIGUES
# =============================
OPENLIGA_BASE = "https://api.openligadb.de"

def fetch_openliga_leagues():
    try:
        return requests.get(f"{OPENLIGA_BASE}/getavailableleagues", timeout=20).json()
    except:
        return []

def fetch_openliga_matches(league_shortcut):
    try:
        return requests.get(f"{OPENLIGA_BASE}/getmatchdata/{league_shortcut}/{SEASON}", timeout=20).json()
    except:
        return []

# =============================
# ESPN - MATCHS DU JOUR
# =============================
ESPN_BASE = "http://site.api.espn.com/apis/site/v2/sports"

TOP_LEAGUES = {
    "Champions League": "soccer/uefa.champions",
    "Premier League": "soccer/eng.1",
    "La Liga": "soccer/esp.1",
    "Serie A": "soccer/ita.1",
    "Bundesliga": "soccer/ger.1",
    "Ligue 1": "soccer/fra.1"
}

def fetch_espn_today_matches(league_api):
    today = datetime.utcnow().strftime("%Y%m%d")
    url = f"{ESPN_BASE}/{league_api}/scoreboard?dates={today}"
    try:
        res = requests.get(url, timeout=20).json()
        return res.get("events", [])
    except:
        return []

# =============================
# SCORE
# =============================
def get_score(match):
    if "MatchResults" in match and match["MatchResults"]:
        r = match["MatchResults"][-1]
        return f'{r["PointsTeam1"]}-{r["PointsTeam2"]}'
    elif "competitions" in match and match["competitions"]:
        comp = match["competitions"][0]
        if "competitors" in comp:
            try:
                home = comp["competitors"][0]["score"]
                away = comp["competitors"][1]["score"]
                return f"{home}-{away}"
            except:
                return "Non joué"
    return "Non joué"

# =============================
# H2H et forme
# =============================
def get_h2h(team1, team2, all_matches, limit=5):
    h2h = []
    for m in reversed(all_matches):
        t1 = m["Team1"]["TeamName"]
        t2 = m["Team2"]["TeamName"]
        if {t1, t2} == {team1, team2} and m.get("MatchResults"):
            r = m["MatchResults"][-1]
            h2h.append(f"{t1} {r['PointsTeam1']}-{r['PointsTeam2']} {t2}")
            if len(h2h) >= limit:
                break
    return h2h if h2h else ["Aucun historique"]

def get_form(team, all_matches, limit=5):
    form = []
    for m in reversed(all_matches):
        if m.get("MatchResults"):
            t1 = m["Team1"]["TeamName"]
            t2 = m["Team2"]["TeamName"]
            r = m["MatchResults"][-1]
            if team == t1:
                form.append("V" if r["PointsTeam1"] > r["PointsTeam2"] else
                            "N" if r["PointsTeam1"] == r["PointsTeam2"] else "D")
            elif team == t2:
                form.append("V" if r["PointsTeam2"] > r["PointsTeam1"] else
                            "N" if r["PointsTeam1"] == r["PointsTeam2"] else "D")
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

def format_match_message(match, all_matches, league_name, team1, team2, score):
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
    # 1️⃣ OpenLigaDB - toutes les ligues
    leagues = fetch_openliga_leagues()
    for league in leagues:
        league_name = league.get("LeagueName") or league.get("LeagueShortName") or league.get("LeagueShortcut")
        league_shortcut = league.get("LeagueShortcut") or league.get("LeagueId")
        if not league_name or not league_shortcut:
            continue

        all_matches = fetch_openliga_matches(league_shortcut)
        if not all_matches:
            continue

        send_to_telegram(f"🏆 {league_name} – Saison {SEASON}")
        for match in all_matches:
            try:
                team1 = match["Team1"]["TeamName"]
                team2 = match["Team2"]["TeamName"]
                score = get_score(match)
                msg = format_match_message(match, all_matches, league_name, team1, team2, score)
                send_to_telegram(msg)
            except:
                continue

    # 2️⃣ ESPN - Top ligues et CL pour aujourd'hui
    for league_name, api_path in TOP_LEAGUES.items():
        espn_matches = fetch_espn_today_matches(api_path)
        if not espn_matches:
            continue

        send_to_telegram(f"🏆 {league_name} – Matchs du jour (ESPN)")
        for m in espn_matches:
            try:
                comp = m["competitions"][0]
                team1 = comp["competitors"][0]["team"]["displayName"]
                team2 = comp["competitors"][1]["team"]["displayName"]
                score = get_score(m)
                msg = f"⚽ {team1} vs {team2}\n📊 Score : {score}"
                send_to_telegram(msg)
            except:
                continue

    send_to_telegram("✅ Analyse terminée pour toutes les ligues et top matchs ESPN.")

if __name__ == "__main__":
    main()
