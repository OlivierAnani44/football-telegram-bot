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
import os
import sys
import requests
import datetime
from typing import List, Dict

# =========================
# Variables d'environnement
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Variables BOT_TOKEN ou CHANNEL_ID manquantes")
    sys.exit(1)

# =========================
# Paramètres généraux
# =========================
LEAGUES = ["eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "por.1", "ned.1", "uefa.champions"]
TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")
MAX_DRAW_RISK = 1  # max 1 match nul dans combiné RISK

# =========================
# Fonctions utilitaires
# =========================
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, data=data)
    if resp.status_code != 200:
        print(f"[TELEGRAM] status={resp.status_code} response={resp.text}")

def fetch_matches(league: str) -> List[Dict]:
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"[ERROR] Impossible de récupérer {league}")
        return []
    data = resp.json()
    events = data.get("events", [])
    return [e for e in events if e["date"].startswith(TODAY)]

def compute_confidence(home_stats: Dict, away_stats: Dict) -> float:
    """Compare toutes les stats et retourne une confiance entre 0 et 10"""
    scoreH, scoreA = 0, 0
    weight = {
        "goals": 2, "shots": 1, "shotsOnGoal": 1, "possession": 0.5,
        "corners": 0.5, "fouls": -0.2, "yellowCards": -0.1,
        "redCards": -0.3, "passes": 0.5, "passPct": 0.5
    }
    for k in weight.keys():
        valH = home_stats.get(k, 0)
        valA = away_stats.get(k, 0)
        if k in ["fouls", "yellowCards", "redCards"]:
            if valH < valA: scoreH += weight[k]
            else: scoreA += weight[k]
        else:
            if valH > valA: scoreH += weight[k]
            else: scoreA += weight[k]
    scoreH += 0.5  # avantage domicile
    total = scoreH + scoreA
    return round((scoreH / total if total else 0.5) * 10, 1)

def analyze_match(event: Dict) -> Dict:
    """Analyse complète d'un match avec stats détaillées"""
    try:
        comp = event["competitions"][0]
        home = comp["competitors"][0]
        away = comp["competitors"][1]

        teamH = home["team"]["displayName"]
        teamA = away["team"]["displayName"]

        stats_home = {s["name"]: float(s.get("value",0)) for s in home.get("statistics",[])}
        stats_away = {s["name"]: float(s.get("value",0)) for s in away.get("statistics",[])}

        confidence = compute_confidence(stats_home, stats_away)

        # Pronostic
        pick = "Match nul"
        if stats_home.get("goals",0) > stats_away.get("goals",0):
            pick = f"{teamH} gagne"
        elif stats_home.get("goals",0) < stats_away.get("goals",0):
            pick = f"{teamA} gagne"

        odds = round(1/(confidence/10+0.01),2)

        # Statistiques détaillées
        detailed_stats = {}
        for k in set(list(stats_home.keys()) + list(stats_away.keys())):
            detailed_stats[k] = f"{stats_home.get(k,'N/A')} - {stats_away.get(k,'N/A')}"

        league_name = event.get("league", {}).get("name") or event.get("leagueName","Inconnue")

        return {
            "league": league_name,
            "teams": f"{teamH} vs {teamA}",
            "score": f"{home.get('score','0')} - {away.get('score','0')}",
            "stats": detailed_stats,
            "pronostic": pick,
            "confidence": confidence,
            "odds": odds
        }
    except Exception as e:
        print(f"[ERROR] Analyse match échouée: {e}")
        return {}

def generate_combinés(matches: List[Dict]):
    risk_matches, medium_matches = [], []
    draw_count = 0
    for m in matches:
        if not m: continue
        # Combiné RISK
        if "nul" in m["pronostic"].lower():
            if draw_count < MAX_DRAW_RISK:
                risk_matches.append(m)
                draw_count += 1
        else:
            risk_matches.append(m)
        # Combiné MEDIUM
        if m["confidence"] >= 6:
            medium_matches.append(m)
    return medium_matches, risk_matches

# =========================
# Main
# =========================
def main():
    all_matches = []
    for league in LEAGUES:
        events = fetch_matches(league)
        print(f"[INFO] {league} → {len(events)} matchs trouvés")
        for e in events:
            analyzed = analyze_match(e)
            if not analyzed: continue
            all_matches.append(analyzed)

            msg = f"🏆 {analyzed['league']}\n⚽ {analyzed['teams']}\n📊 Score : {analyzed['score']}\n\n📈 Statistiques détaillées :\n"
            for k,v in analyzed["stats"].items():
                msg += f"{k}: {v}\n"
            msg += f"\n🔮 Pronostic : {analyzed['pronostic']}\n🎯 Confiance : {analyzed['confidence']}/10\n💰 Cote : {analyzed['odds']}"
            send_telegram(msg)

    medium, risk = generate_combinés(all_matches)

    if risk:
        msg = "🔴 COMBINÉ RISK\n\n"
        for i,m in enumerate(risk,1):
            msg += f"{i}️⃣ {m['teams']}\n➡️ {m['pronostic']}\n🎯 Confiance : {m['confidence']}/10\n💰 Cote : {m['odds']}\n\n"
        total_odds = 1
        for m in risk:
            total_odds *= m['odds']
        msg += f"📊 COTE TOTALE : {round(total_odds,2)}"
        send_telegram(msg)

    if medium:
        msg = "🟢 COMBINÉ MEDIUM\n\n"
        for i,m in enumerate(medium,1):
            msg += f"{i}️⃣ {m['teams']}\n➡️ {m['pronostic']}\n🎯 Confiance : {m['confidence']}/10\n💰 Cote : {m['odds']}\n\n"
        total_odds = 1
        for m in medium:
            total_odds *= m['odds']
        msg += f"📊 COTE TOTALE : {round(total_odds,2)}"
        send_telegram(msg)

if __name__=="__main__":
    print("🚀 Bot démarré")
    main()
