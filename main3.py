import requests
import datetime
import os
import sys
from typing import List, Tuple, Dict, Any

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# debug pour confirmer que les variables existent
print("DEBUG BOT_TOKEN:", "OK" if BOT_TOKEN else "MANQUANT")
print("DEBUG CHANNEL_ID:", "OK" if CHANNEL_ID else "MANQUANT")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Variables BOT_TOKEN ou CHANNEL_ID manquantes")
    sys.exit(1)

# ================= CONFIG =================
LEAGUES = [
    "uefa.champions",
    "eng.1",
    "esp.1",
    "ita.1",
    "ger.1",
    "fra.1",
    "por.1",
    "ned.1"
]

BIG_TEAMS = [
    "Real Madrid", "Barcelona", "Manchester City", "Bayern Munich",
    "Paris Saint-Germain", "Liverpool", "Arsenal", "Inter",
    "Juventus", "AC Milan", "Chelsea", "Borussia Dortmund"
]

# ================= UTILS =================
def log(msg: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def send_telegram(message: str) -> bool:
    """Send message to Telegram channel"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        r.raise_for_status()
        log(f"[TELEGRAM] Message envoyé (status={r.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        log(f"[ERROR TELEGRAM] Erreur d'envoi: {e}")
        return False

def get_matches_today(league: str) -> List[Dict]:
    """Get today's matches for a specific league"""
    today = datetime.date.today().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={today}"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        events = data.get("events", [])
        log(f"[INFO] {league} → {len(events)} match(s) trouvé(s)")
        return events
    except requests.exceptions.RequestException as e:
        log(f"[ERROR] {league} → Erreur réseau: {e}")
        return []
    except ValueError as e:
        log(f"[ERROR] {league} → Erreur JSON: {e}")
        return []

def get_team_form(team_id: str, league: str) -> Dict[str, int]:
    """Get team form from last 5 matches"""
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team_id}/schedule"
    
    wins = draws = losses = gf = ga = 0
    matches_analyzed = 0
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Take only completed matches
        completed_matches = [e for e in data.get("events", []) 
                           if e.get("status", {}).get("type", {}).get("completed")]
        
        for e in completed_matches[:5]:  # Last 5 completed matches
            try:
                comp = e["competitions"][0]["competitors"]
                if len(comp) < 2:
                    continue
                    
                h, a = comp[0], comp[1]
                h_score = int(h.get("score", "0"))
                a_score = int(a.get("score", "0"))
                
                if h["team"]["id"] == team_id:
                    sf, sa = h_score, a_score
                else:
                    sf, sa = a_score, h_score
                
                gf += sf
                ga += sa
                
                if sf > sa:
                    wins += 1
                elif sf < sa:
                    losses += 1
                else:
                    draws += 1
                    
                matches_analyzed += 1
            except (KeyError, ValueError, IndexError) as e:
                log(f"[WARN] Erreur analyse match: {e}")
                continue
                
    except requests.exceptions.RequestException:
        log(f"[WARN] Impossible de récupérer les stats pour l'équipe {team_id}")
    except ValueError:
        log(f"[WARN] Données JSON invalides pour l'équipe {team_id}")
    
    return {
        "wins": wins, 
        "draws": draws, 
        "losses": losses, 
        "gf": gf, 
        "ga": ga,
        "matches_analyzed": matches_analyzed
    }

def calculate_confidence_score(formH: Dict, formA: Dict, teamH: str, teamA: str) -> float:
    """Calculate confidence score with weighted factors"""
    score = 5.0  # Base score
    
    # Form factor (40%)
    if formH["matches_analyzed"] > 0 and formA["matches_analyzed"] > 0:
        form_ratio_h = formH["wins"] / formH["matches_analyzed"] if formH["matches_analyzed"] > 0 else 0
        form_ratio_a = formA["wins"] / formA["matches_analyzed"] if formA["matches_analyzed"] > 0 else 0
        score += (form_ratio_h - form_ratio_a) * 2.0
    
    # Goal difference factor (30%)
    gd_h = formH["gf"] - formH["ga"]
    gd_a = formA["gf"] - formA["ga"]
    score += (gd_h - gd_a) * 0.05
    
    # Home advantage (15%)
    score += 0.8
    
    # Big team factor (15%)
    if teamH in BIG_TEAMS:
        score += 0.7
    if teamA in BIG_TEAMS:
        score -= 0.7
    
    # Normalize between 1 and 10
    return max(1.0, min(10.0, score))

def predict_match(teamH: str, teamA: str, formH: Dict, formA: Dict) -> Tuple[str, float, float]:
    """Predict match outcome with confidence and odds"""
    confidence = calculate_confidence_score(formH, formA, teamH, teamA)
    
    # Determine pick based on confidence
    if confidence >= 6.5:
        pick = f"{teamH} gagne"
    elif confidence <= 3.5:
        pick = f"{teamA} gagne"
    else:
        # Balanced match - determine based on form
        h_strength = formH["wins"] * 3 + formH["draws"]
        a_strength = formA["wins"] * 3 + formA["draws"]
        
        if abs(h_strength - a_strength) <= 2:  # Very close
            pick = "Match nul"
        elif h_strength > a_strength:
            pick = f"{teamH} gagne"
        else:
            pick = f"{teamA} gagne"
    
    # Calculate odds (simplified model)
    odds = round(1 / (confidence / 10), 2)
    
    return pick, round(confidence, 1), odds

# ================= MAIN =================
def main():
    log("🚀 Bot de pronostics démarré")
    send_telegram("✅ <b>Bot pronostics actif</b>")
    
    medium_bets = []
    risk_bets = []
    all_matches = []
    
    log("📊 Récupération des matchs du jour...")
    
    # Collect all matches
    for league in LEAGUES:
        events = get_matches_today(league)
        for match in events:
            try:
                comp = match["competitions"][0]
                h, a = comp["competitors"]
                
                teamH = h["team"]["displayName"]
                teamA = a["team"]["displayName"]
                teamH_id = h["team"]["id"]
                teamA_id = a["team"]["id"]
                
                # Skip if match already started
                status = match.get("status", {}).get("type", {})
                if status.get("id") != "1":  # 1 = scheduled, 2 = in progress, 3 = finished
                    log(f"[SKIP] {teamH} vs {teamA} - Match déjà commencé ou terminé")
                    continue
                
                # Get team forms
                formH = get_team_form(teamH_id, league)
                formA = get_team_form(teamA_id, league)
                
                # Make prediction
                pick, confidence, odds = predict_match(teamH, teamA, formH, formA)
                
                log(f"[MATCH] {teamH} vs {teamA} → {confidence}/10 → {pick} (cote: {odds})")
                
                all_matches.append({
                    "home": teamH,
                    "away": teamA,
                    "pick": pick,
                    "confidence": confidence,
                    "odds": odds,
                    "league": league
                })
                
            except KeyError as e:
                log(f"[ERROR] Données manquantes pour un match: {e}")
                continue
            except Exception as e:
                log(f"[ERROR] Erreur traitement match: {e}")
                continue
    
    # Sort matches by confidence
    all_matches.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Select bets for medium combo (top 3 with confidence >= 6)
    for match in all_matches:
        if match["confidence"] >= 6.0 and len(medium_bets) < 3:
            medium_bets.append(match)
    
    # Select bets for risk combo (next 5 with confidence >= 4.5)
    for match in all_matches:
        if match not in medium_bets and match["confidence"] >= 4.5 and len(risk_bets) < 5:
            risk_bets.append(match)
    
    # Send results
    def format_combo(title: str, bets: List[Dict]) -> str:
        if not bets:
            return f"<b>{title}</b>\n\nAucun pronostic sélectionné aujourd'hui."
        
        message = f"<b>{title}</b>\n\n"
        total_odds = 1.0
        
        for i, bet in enumerate(bets, 1):
            total_odds *= bet["odds"]
            message += (
                f"<b>{i}️⃣ {bet['home']} vs {bet['away']}</b>\n"
                f"🏆 Ligue: {bet['league']}\n"
                f"🎯 <b>Pronostic:</b> {bet['pick']}\n"
                f"📈 Confiance: <b>{bet['confidence']}/10</b>\n"
                f"💰 Cote: <b>{bet['odds']}</b>\n\n"
            )
        
        message += f"📊 <b>COTE TOTALE: {round(total_odds, 2)}</b>\n"
        message += f"💰 <b>Mise recommandée: {round(10/total_odds, 2)}€</b>"
        
        return message
    
    # Send combos
    if medium_bets:
        send_telegram(format_combo("🔵 COMBINÉ MEDIUM", medium_bets))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic MEDIUM aujourd'hui</b>")
    
    if risk_bets:
        send_telegram(format_combo("🔴 COMBINÉ RISK", risk_bets))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic RISK aujourd'hui</b>")
    
    log(f"✅ Terminé: {len(medium_bets)} pronostic(s) MEDIUM, {len(risk_bets)} pronostic(s) RISK")

if __name__ == "__main__":
    main()