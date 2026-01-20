# main.py - Version Premium Multi-ligues pour Telegram
# Assurez-vous d'avoir défini les variables d'environnement : BOT_TOKEN et CHANNEL_ID

import os
import requests
from datetime import datetime
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError("❌ Variables BOT_TOKEN ou CHANNEL_ID manquantes")

API_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/scoreboard"  # exemple général
LEAGUES = [
    "eng.1", "esp.1", "ita.1", "ger.1", "fra.1",
    "por.1", "ned.1", "uefa.champions"
]

def debug(msg):
    print(f"[DEBUG] {msg}")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": msg, "parse_mode": "HTML"}
    r = requests.post(url, json=payload)
    debug(f"[TELEGRAM] status={r.status_code} response={r.text}")
    return r.status_code == 200

def fetch_matches(league):
    today = datetime.utcnow().strftime("%Y%m%d")
    params = {"league": league, "dates": today}
    try:
        r = requests.get(API_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        events = data.get("events", [])
        debug(f"[INFO] {league} → {len(events)} matchs trouvés")
        return events
    except Exception as e:
        debug(f"[ERROR] fetch_matches {league}: {e}")
        return []

def extract_stat(stat_list, key_name):
    if not isinstance(stat_list, list):
        return "N/A"
    for stat in stat_list:
        if stat.get("name") == key_name:
            return stat.get("value", "N/A")
    return "N/A"

def analyze_match(event):
    try:
        comps = event.get("competitions", [])
        if not comps:
            return None

        comp = comps[0]
        home = comp["competitors"][0]
        away = comp["competitors"][1]

        stats_home = home.get("statistics", [])
        stats_away = away.get("statistics", [])

        # Comparaison simple : tirs, possession, buts
        home_shots = extract_stat(stats_home, "shots")
        away_shots = extract_stat(stats_away, "shots")
        home_poss = extract_stat(stats_home, "possession")
        away_poss = extract_stat(stats_away, "possession")
        home_goals = int(home.get("score", 0))
        away_goals = int(away.get("score", 0))

        # Calcul confiance
        score_dom = 0
        score_ext = 0
        if isinstance(home_shots, int) and isinstance(away_shots, int):
            score_dom += home_shots > away_shots
            score_ext += away_shots > home_shots
        if isinstance(home_poss, (int,float)) and isinstance(away_poss,(int,float)):
            score_dom += home_poss > away_poss
            score_ext += away_poss > home_poss
        score_dom += home_goals > away_goals
        score_ext += away_goals > home_goals

        total = max(score_dom + score_ext, 1)
        confiance = round(max(score_dom, score_ext) / total * 10, 1)

        if score_dom > score_ext:
            pronostic = f"{home['team']['displayName']} gagne"
        elif score_dom < score_ext:
            pronostic = f"{away['team']['displayName']} gagne"
        else:
            pronostic = "Match nul"

        league_name = event.get("league", {}).get("name") or event.get("leagueName") or "Inconnue"

        return {
            "league": league_name,
            "home_team": home["team"]["displayName"],
            "away_team": away["team"]["displayName"],
            "score": f"{home_goals}-{away_goals}",
            "stats": {
                "tirs": f"{home_shots} - {away_shots}",
                "possession": f"{home_poss}% - {away_poss}%"
            },
            "pronostic": pronostic,
            "confiance": confiance
        }
    except Exception as e:
        debug(f"[ERROR] analyze_match: {e}")
        return None

def generate_combine(matches, type_="MEDIUM"):
    combine_msg = f"🟢 COMBINÉ {type_}\n\n"
    cote_total = 1.0
    for i, m in enumerate(matches, 1):
        combine_msg += f"{i}️⃣ {m['home_team']} vs {m['away_team']}\n"
        combine_msg += f"➡️ {m['pronostic']}\n"
        combine_msg += f"🎯 Confiance : {m['confiance']}/10\n"
        cote = 1 + (10 - m['confiance'])/10  # simplification cote
        combine_msg += f"💰 Cote : {round(cote,2)}\n\n"
        cote_total *= cote
    combine_msg += f"📊 COTE TOTALE : {round(cote_total,2)}"
    return combine_msg

def main():
    debug(f"BOT_TOKEN OK: {bool(BOT_TOKEN)}")
    debug(f"CHANNEL_ID OK: {bool(CHANNEL_ID)}")
    all_matches = []
    for league in LEAGUES:
        events = fetch_matches(league)
        for e in events:
            analyzed = analyze_match(e)
            if analyzed:
                all_matches.append(analyzed)
                msg = f"🏆 {analyzed['league']}\n⚽ {analyzed['home_team']} vs {analyzed['away_team']}\n📊 Score : {analyzed['score']}\n📈 Statistiques :\nTirs: {analyzed['stats']['tirs']}\nPossession: {analyzed['stats']['possession']}\n🔮 Pronostic : {analyzed['pronostic']}\nConfiance : {analyzed['confiance']}/10"
                send_telegram(msg)
        time.sleep(1)

    if all_matches:
        # MEDIUM combine
        med_combine = generate_combine(all_matches[:5], "MEDIUM")
        send_telegram(med_combine)
        # RISK combine
        risk_combine = generate_combine(all_matches[:5], "RISK")
        send_telegram(risk_combine)
    else:
        debug("[INFO] Aucun match à analyser aujourd'hui")

if __name__ == "__main__":
    debug("🚀 Bot démarré")
    main()
