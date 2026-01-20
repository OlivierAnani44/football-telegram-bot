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
# ESPN - TOP LIGUES & CHAMPIONS LEAGUE
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
# Récupérer les matchs du jour
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
# Récupérer les statistiques détaillées d’un match
# =============================
def fetch_match_stats(league_api, game_id):
    url = f"{ESPN_BASE}/{league_api}/summary?event={game_id}"
    try:
        res = requests.get(url, timeout=20).json()
        stats = {}
        # Extraire stats principales
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
# Formater message Telegram avec stats
# =============================
def format_espn_match_message(match, league_api):
    try:
        comp = match["competitions"][0]
        team1 = comp["competitors"][0]["team"]["displayName"]
        team2 = comp["competitors"][1]["team"]["displayName"]
        score = comp["competitors"][0]["score"] + "-" + comp["competitors"][1]["score"]

        # Récupérer stats détaillées
        stats = fetch_match_stats(league_api, match["id"])

        stats_text = ""
        if stats:
            t1_stats = stats.get(team1, {})
            t2_stats = stats.get(team2, {})
            all_keys = set(list(t1_stats.keys()) + list(t2_stats.keys()))
            for k in all_keys:
                stats_text += f"{k}: {t1_stats.get(k,'N/A')} - {t2_stats.get(k,'N/A')}\n"

        message = f"""
🏆 {league_api.replace('soccer/', '')}
⚽ {team1} vs {team2}
📊 Score : {score}

📈 Statistiques :
{stats_text.strip() if stats_text else 'Non disponible'}

🔮 Analyse simple :
Avantage probable : {'Équilibré' if not stats else 'À définir selon stats'}
""".strip()
        return message
    except:
        return None

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
