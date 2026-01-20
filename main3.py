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
