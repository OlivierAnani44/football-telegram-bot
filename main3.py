import os
import sys
import requests
import datetime
import random
from typing import Dict, List

# =========================
# Variables d'environnement
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

print("DEBUG BOT_TOKEN:", "OK" if BOT_TOKEN else "MANQUANT")
print("DEBUG CHANNEL_ID:", "OK" if CHANNEL_ID else "MANQUANT")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Variables BOT_TOKEN ou CHANNEL_ID manquantes")
    sys.exit(1)

# =========================
# Paramètres généraux
# =========================
MAX_DRAW_RISK = 1
LEAGUES = [
    "eng.1", "esp.1", "ita.1", "ger.1", "fra.1",
    "por.1", "ned.1", "uefa.champions", "uefa.europa"
]
TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")

# =========================
# Fonctions utilitaires
# =========================
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, data=data)
    if resp.status_code != 200:
        print(f"[TELEGRAM] status={resp.status_code} response={resp.text}")
    else:
        print(f"[TELEGRAM] Message envoyé: {message.splitlines()[0]}")

def fetch_matches(league: str) -> List[Dict]:
    """Récupère tous les matchs de la journée pour une ligue"""
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"[ERROR] Impossible de récupérer {league}")
        return []
    data = resp.json()
    events = data.get("events", [])
    today_events = [e for e in events if e["date"].startswith(TODAY)]
    return today_events

def analyze_match(event: Dict) -> Dict:
    """Analyse complète des statistiques d'un match domicile vs extérieur"""
    try:
        home = event["competitions"][0]["competitors"][0]
        away = event["competitions"][0]["competitors"][1]

        teamH = home["team"]["displayName"]
        teamA = away["team"]["displayName"]

        # Récupération stats
        stats_home = {s["name"]: float(s.get("value", 0)) for s in home.get("statistics", [])}
        stats_away = {s["name"]: float(s.get("value", 0)) for s in away.get("statistics", [])}

        # Comparaison statistique
        scoreH, scoreA = 0, 0
        weight = {
            "goals": 2, "shots": 1, "shotsOnGoal": 1, "possession": 0.5,
            "corners": 0.5, "fouls": -0.2, "yellowCards": -0.1,
            "redCards": -0.3, "passes": 0.5, "passPct": 0.5
        }

        for k in weight.keys():
            valH = stats_home.get(k, 0)
            valA = stats_away.get(k, 0)
            if k in ["fouls", "yellowCards", "redCards"]:
                if valH < valA: scoreH += weight[k]
                else: scoreA += weight[k]
            else:
                if valH > valA: scoreH += weight[k]
                else: scoreA += weight[k]

        scoreH += 0.5  # avantage domicile
        total = scoreH + scoreA
        prob_dom = scoreH / total if total else 0.5
        prob_ext = scoreA / total if total else 0.5
        prob_draw = max(0, 1 - (prob_dom + prob_ext))

        r = random.random()
        pick = "Match nul"
        if r < prob_dom:
            pick = f"{teamH} gagne"
        elif r < prob_dom + prob_ext:
            pick = f"{teamA} gagne"

        confidence = round(max(prob_dom, prob_ext, prob_draw)*10, 1)
        odds = round(1 / (max(prob_dom, prob_ext, prob_draw) + 0.01), 2)

        detailed_stats = {}
        for s in set(list(stats_home.keys()) + list(stats_away.keys())):
            detailed_stats[s] = f"{stats_home.get(s, 'N/A')} - {stats_away.get(s, 'N/A')}"

        # Gestion sûre du nom de la ligue
        league_name = event.get("league", {}).get("name") or event.get("leagueName", "Inconnue")

        return {
            "league": league_name,
            "teams": f"{teamH} vs {teamA}",
            "score": f"{home.get('score', '0')} - {away.get('score', '0')}",
            "stats": detailed_stats,
            "pronostic": pick,
            "confidence": confidence,
            "odds": odds
        }
    except Exception as ex:
        print(f"[ERROR] Analyse match échouée: {ex}")
        return {}

# =========================
# Génération combinés
# =========================
def generate_combinés(matches: List[Dict]):
    risk_matches, medium_matches = [], []
    draw_count = 0
    for m in matches:
        if not m: continue
        if "nul" in m["pronostic"].lower():
            if draw_count < MAX_DRAW_RISK:
                risk_matches.append(m)
                draw_count += 1
            else:
                if m["stats"].get("goals", "0 - 0") != "0 - 0":
                    risk_matches.append(m)
        else:
            risk_matches.append(m)
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

            # Envoi sur Telegram
            msg = f"🏆 {analyzed['league']}\n⚽ {analyzed['teams']}\n📊 Score : {analyzed['score']}\n\n📈 Statistiques :\n"
            for k,v in analyzed["stats"].items():
                msg += f"{k}: {v}\n"
            msg += f"\n🔮 Pronostic : {analyzed['pronostic']}\n🎯 Confiance : {analyzed['confidence']}/10\n💰 Cote estimée : {analyzed['odds']}"
            send_telegram(msg)

    # Génération combinés
    medium, risk = generate_combinés(all_matches)
    if risk:
        msg = "🔴 COMBINÉ RISK\n\n"
        for i, m in enumerate(risk,1):
            msg += f"{i}️⃣ {m['teams']}\n➡️ {m['pronostic']}\n🎯 Confiance : {m['confidence']}/10\n💰 Cote : {m['odds']}\n\n"
        total_odds = 1
        for m in risk:
            total_odds *= m['odds']
        msg += f"📊 COTE TOTALE : {round(total_odds,2)}"
        send_telegram(msg)

    if medium:
        msg = "🟢 COMBINÉ MEDIUM\n\n"
        for i, m in enumerate(medium,1):
            msg += f"{i}️⃣ {m['teams']}\n➡️ {m['pronostic']}\n🎯 Confiance : {m['confidence']}/10\n💰 Cote : {m['odds']}\n\n"
        total_odds = 1
        for m in medium:
            total_odds *= m['odds']
        msg += f"📊 COTE TOTALE : {round(total_odds,2)}"
        send_telegram(msg)

if __name__ == "__main__":
    print("🚀 Bot démarré")
    main()
