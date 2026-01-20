import os
import requests
from datetime import datetime

# =============================
# CONFIGURATION
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

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
# ESPN - TOP LIGUES + CL
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

# =============================
# Récupérer matchs du jour
# =============================
def fetch_espn_today_matches(league_api):
    today = datetime.utcnow().strftime("%Y%m%d")
    url = f"{ESPN_BASE}/{league_api}/scoreboard?dates={today}"
    try:
        res = requests.get(url, timeout=20).json()
        return res.get("events", [])
    except:
        return []

# =============================
# Récupérer stats détaillées
# =============================
def fetch_match_stats(league_api, game_id):
    url = f"{ESPN_BASE}/{league_api}/summary?event={game_id}"
    try:
        res = requests.get(url, timeout=20).json()
        stats = {}
        if "boxscore" in res:
            teams = res["boxscore"].get("teams", [])
            for t in teams:
                team_name = t["team"]["displayName"]
                team_stats = {}
                for s in t.get("statistics", []):
                    team_stats[s["name"]] = s.get("displayValue", "N/A")
                stats[team_name] = team_stats
        return stats
    except:
        return {}

# =============================
# Formater message Telegram
# =============================
def format_espn_match_message(match, league_api):
    try:
        comp = match["competitions"][0]
        team1 = comp["competitors"][0]["team"]["displayName"]
        team2 = comp["competitors"][1]["team"]["displayName"]
        score = f"{comp['competitors'][0].get('score','0')}-{comp['competitors'][1].get('score','0')}"

        stats_json = fetch_match_stats(league_api, match["id"])

        # Mapping stat → lisible
        stat_fields = {
            "shots": "Tirs",
            "shotsOnGoal": "Tirs cadrés",
            "possession": "Possession (%)",
            "corners": "Corners",
            "fouls": "Fautes",
            "yellowCards": "Cartons jaunes",
            "redCards": "Cartons rouges",
            "offsides": "Hors-jeu",
            "passes": "Passes",
            "passAccuracy": "Précision passes (%)",
            "tackles": "Tacles",
            "goalAssists": "Passes décisives",
            "goals": "Buts"
        }

        stats_text = ""
        for field, label in stat_fields.items():
            val1 = stats_json.get(team1, {}).get(field, "N/A")
            val2 = stats_json.get(team2, {}).get(field, "N/A")
            stats_text += f"{label}: {val1} - {val2}\n"

        message = f"""
🏆 {league_api.replace('soccer/', '').title()}
⚽ {team1} vs {team2}
📊 Score : {score}

📈 Statistiques détaillées :
{stats_text.strip()}

🔮 Analyse simple :
Avantage probable : {'Équilibré' if not stats_json else 'À définir selon stats'}
""".strip()
        return message
    except Exception as e:
        return f"Erreur format match: {e}"

# =============================
# MAIN
# =============================
def main():
    for league_name, league_api in TOP_LEAGUES.items():
        matches = fetch_espn_today_matches(league_api)
        if not matches:
            continue

        send_to_telegram(f"🏆 {league_name} – Matchs du jour")
        for match in matches:
            msg = format_espn_match_message(match, league_api)
            if msg:
                send_to_telegram(msg)

    send_to_telegram("✅ Analyse terminée pour la Ligue des Champions et top ligues ESPN.")

if __name__ == "__main__":
    main()
