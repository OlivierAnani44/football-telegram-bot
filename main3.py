import requests
import datetime
import os
import sys
import statistics
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
        events = data.get("events", [])
        if not events:
            return {"wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "matches_analyzed": 0}
        
        completed_matches = []
        for e in events:
            try:
                status_type = e.get("status", {}).get("type", {})
                if status_type.get("completed") == True or status_type.get("id") == "3":
                    completed_matches.append(e)
            except:
                continue
        
        for e in completed_matches[:5]:  # Last 5 completed matches
            try:
                comp = e.get("competitions", [{}])[0].get("competitors", [])
                if len(comp) < 2:
                    continue
                    
                h, a = comp[0], comp[1]
                h_score = int(h.get("score", "0"))
                a_score = int(a.get("score", "0"))
                
                if h.get("team", {}).get("id") == team_id:
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
            except (KeyError, ValueError, IndexError, AttributeError) as e:
                log(f"[WARN] Erreur analyse match: {e}")
                continue
                
    except requests.exceptions.RequestException:
        log(f"[WARN] Impossible de récupérer les stats pour l'équipe {team_id}")
    except ValueError:
        log(f"[WARN] Données JSON invalides pour l'équipe {team_id}")
    except Exception as e:
        log(f"[WARN] Erreur générale get_team_form: {e}")
    
    return {
        "wins": wins, 
        "draws": draws, 
        "losses": losses, 
        "gf": gf, 
        "ga": ga,
        "matches_analyzed": matches_analyzed
    }

def calculate_confidence_score(formH: Dict, formA: Dict, teamH: str, teamA: str, league: str) -> Dict[str, float]:
    """Calculate multiple confidence scores with advanced metrics"""
    
    # Initial scores
    scores = {
        "home_win": 5.0,
        "draw": 5.0,
        "away_win": 5.0
    }
    
    # Base form analysis (40%)
    if formH["matches_analyzed"] > 0 and formA["matches_analyzed"] > 0:
        home_strength = (formH["wins"] * 3 + formH["draws"]) / formH["matches_analyzed"]
        away_strength = (formA["wins"] * 3 + formA["draws"]) / formA["matches_analyzed"]
        
        form_diff = home_strength - away_strength
        
        scores["home_win"] += form_diff * 2.0
        scores["away_win"] -= form_diff * 2.0
    
    # Goal metrics (30%)
    if formH["matches_analyzed"] > 0:
        home_avg_gf = formH["gf"] / formH["matches_analyzed"]
        home_avg_ga = formH["ga"] / formH["matches_analyzed"]
    else:
        home_avg_gf = home_avg_ga = 1.5
    
    if formA["matches_analyzed"] > 0:
        away_avg_gf = formA["gf"] / formA["matches_analyzed"]
        away_avg_ga = formA["ga"] / formA["matches_analyzed"]
    else:
        away_avg_gf = away_avg_ga = 1.5
    
    # Expected goals analysis
    expected_home_goals = (home_avg_gf + away_avg_ga) / 2
    expected_away_goals = (away_avg_gf + home_avg_ga) / 2
    
    goal_diff = expected_home_goals - expected_away_goals
    scores["home_win"] += goal_diff * 0.5
    scores["away_win"] -= goal_diff * 0.5
    
    # Draw likelihood based on goal expectations
    # Matches with close expected goals are more likely to draw
    goal_proximity = 1.0 - min(1.0, abs(goal_diff) / 3.0)
    scores["draw"] += goal_proximity * 1.5
    
    # Home advantage (15%)
    scores["home_win"] += 1.2
    scores["draw"] += 0.4
    
    # Team reputation (10%)
    if teamH in BIG_TEAMS:
        scores["home_win"] += 1.5
        scores["draw"] += 0.3
    if teamA in BIG_TEAMS:
        scores["away_win"] += 1.5
        scores["draw"] += 0.3
    
    # League-specific adjustments (5%)
    if "champions" in league:
        # Champions League tends to have fewer draws
        scores["draw"] -= 0.5
    
    # Normalize scores
    for key in scores:
        scores[key] = max(1.0, min(10.0, scores[key]))
    
    return scores

def calculate_realistic_odds(confidence_scores: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Calculate realistic betting odds based on confidence scores"""
    
    # Convert scores to probabilities
    total = sum(confidence_scores.values())
    probabilities = {
        "home_win": confidence_scores["home_win"] / total,
        "draw": confidence_scores["draw"] / total,
        "away_win": confidence_scores["away_win"] / total
    }
    
    # Apply bookmaker margin (typically 5-10%)
    margin = 1.05  # 5% margin
    odds = {
        "home_win": round(margin / probabilities["home_win"], 2),
        "draw": round(margin / probabilities["draw"], 2),
        "away_win": round(margin / probabilities["away_win"], 2)
    }
    
    # Ensure minimum odds
    for key in odds:
        if odds[key] < 1.5:
            odds[key] = 1.5
        if odds[key] > 10:
            odds[key] = 10
    
    return odds, probabilities

def predict_match_v2(teamH: str, teamA: str, formH: Dict, formA: Dict, league: str) -> Tuple[str, float, float, Dict[str, float]]:
    """Enhanced prediction with realistic odds"""
    
    # Calculate confidence scores for all outcomes
    confidence_scores = calculate_confidence_score(formH, formA, teamH, teamA, league)
    
    # Calculate realistic odds
    odds, probabilities = calculate_realistic_odds(confidence_scores)
    
    # Determine the most likely outcome
    max_score = max(confidence_scores.values())
    outcomes = list(confidence_scores.keys())
    scores_list = list(confidence_scores.values())
    
    # Get the outcome with highest confidence
    max_index = scores_list.index(max_score)
    best_outcome = outcomes[max_index]
    
    # Map outcome to readable prediction
    outcome_map = {
        "home_win": f"{teamH} gagne",
        "draw": "Match nul",
        "away_win": f"{teamA} gagne"
    }
    
    pick = outcome_map[best_outcome]
    
    # Calculate composite confidence (weighted average)
    composite_confidence = (
        confidence_scores["home_win"] * probabilities["home_win"] +
        confidence_scores["draw"] * probabilities["draw"] +
        confidence_scores["away_win"] * probabilities["away_win"]
    )
    
    # Get odds for the selected outcome
    selected_odds = odds[best_outcome]
    
    return pick, round(composite_confidence, 1), selected_odds, odds

def diversify_predictions(matches: List[Dict]) -> List[Dict]:
    """Ensure prediction diversity in the combo"""
    
    if len(matches) < 3:
        return matches
    
    # Count outcome types
    outcome_counts = {"home_wins": 0, "draws": 0, "away_wins": 0}
    
    for match in matches:
        if "gagne" in match["pick"]:
            if match["home"] in match["pick"]:
                outcome_counts["home_wins"] += 1
            else:
                outcome_counts["away_wins"] += 1
        else:
            outcome_counts["draws"] += 1
    
    # If too many draws, diversify
    max_draws = max(2, len(matches) // 3)  # Max 33% draws
    
    if outcome_counts["draws"] > max_draws:
        sorted_matches = sorted(matches, key=lambda x: x["confidence"], reverse=True)
        
        # Replace some draws with other outcomes
        for match in sorted_matches:
            if outcome_counts["draws"] <= max_draws:
                break
                
            if "Match nul" in match["pick"]:
                # Get alternative odds for this match
                if "all_odds" in match:
                    odds = match["all_odds"]
                    # Choose the next best outcome
                    if odds.get("home_win", 2.0) <= odds.get("away_win", 2.0):
                        new_pick = f"{match['home']} gagne"
                        new_odds = odds.get("home_win", 2.0)
                    else:
                        new_pick = f"{match['away']} gagne"
                        new_odds = odds.get("away_win", 2.0)
                    
                    # Update match
                    match["pick"] = new_pick
                    match["odds"] = new_odds
                    match["confidence"] = match["confidence"] * 0.9  # Slightly reduce confidence
                    
                    outcome_counts["draws"] -= 1
                    
                    if new_pick == f"{match['home']} gagne":
                        outcome_counts["home_wins"] += 1
                    else:
                        outcome_counts["away_wins"] += 1
    
    return matches

def format_improved_combo(title: str, bets: List[Dict], risk_level: str) -> str:
    """Format combo message for Telegram"""
    if not bets:
        return f"<b>{title}</b>\n\nAucun pronostic {risk_level} sélectionné aujourd'hui."
    
    message = f"<b>{title}</b>\n"
    message += f"📅 Date: {datetime.date.today().strftime('%d/%m/%Y')}\n"
    message += f"🎯 Fiabilité: {'Élevée' if risk_level == 'MEDIUM' else 'Modérée'}\n\n"
    
    total_odds = 1.0
    
    for i, bet in enumerate(bets, 1):
        total_odds *= bet["odds"]
        
        # Determine emoji based on prediction type
        if "Match nul" in bet["pick"]:
            outcome_emoji = "⚖️"
        elif bet["home"] in bet["pick"]:
            outcome_emoji = "🏠"
        else:
            outcome_emoji = "✈️"
        
        # Confidence indicator
        confidence_int = int(bet["confidence"])
        conf_bars = "★" * min(5, confidence_int // 2) + "☆" * (5 - min(5, confidence_int // 2))
        
        message += (
            f"{i}. <b>{bet['home']} vs {bet['away']}</b>\n"
            f"   {outcome_emoji} <b>{bet['pick']}</b>\n"
            f"   🏆 {bet.get('league', '?')} | 📊 {conf_bars} ({bet['confidence']}/10)\n"
            f"   💰 Cote: <b>{bet['odds']}</b>\n\n"
        )
    
    # Calculate realistic stake
    if risk_level == "MEDIUM":
        recommended_stake = min(10, max(1, round(15 / total_odds, 2)))
    else:
        recommended_stake = min(5, max(0.5, round(8 / total_odds, 2)))
    
    potential_win = round(recommended_stake * total_odds, 2)
    
    message += (
        f"📈 <b>RÉSUMÉ DU COMBINÉ</b>\n"
        f"├ Nombre de matchs: {len(bets)}\n"
        f"├ Cote totale: <b>{round(total_odds, 2)}</b>\n"
        f"├ Mise recommandée: <b>{recommended_stake}€</b>\n"
        f"└ Gain potentiel: <b>{potential_win}€</b>\n\n"
        f"<i>⚠️ Les paris sportifs comportent des risques</i>"
    )
    
    return message

# ================= MAIN =================
def main():
    log("🚀 Bot de pronostics démarré (version améliorée)")
    send_telegram("✅ <b>Bot pronostics actif - Version 2.0</b>")
    
    medium_bets = []
    risk_bets = []
    all_matches = []
    
    log("📊 Récupération des matchs du jour...")
    
    for league in LEAGUES:
        events = get_matches_today(league)
        for match in events:
            try:
                comp = match.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                
                if len(competitors) < 2:
                    continue
                    
                h, a = competitors[0], competitors[1]
                
                teamH = h.get("team", {}).get("displayName", "Inconnu")
                teamA = a.get("team", {}).get("displayName", "Inconnu")
                teamH_id = h.get("team", {}).get("id")
                teamA_id = a.get("team", {}).get("id")
                
                if not teamH_id or not teamA_id:
                    log(f"[SKIP] {teamH} vs {teamA} - IDs manquants")
                    continue
                
                # Skip if match already started or finished
                status = match.get("status", {})
                status_type = status.get("type", {})
                if status_type.get("id") != "1":  # 1 = scheduled
                    log(f"[SKIP] {teamH} vs {teamA} - Match déjà commencé ou terminé")
                    continue
                
                # Get team forms
                formH = get_team_form(teamH_id, league)
                formA = get_team_form(teamA_id, league)
                
                # Make prediction
                pick, confidence, odds, all_odds = predict_match_v2(
                    teamH, teamA, formH, formA, league
                )
                
                # Extract league name in readable format
                league_parts = league.split(".")
                if len(league_parts) > 1:
                    league_name = league_parts[0].upper()
                else:
                    league_name = league.upper()
                
                match_data = {
                    "home": teamH,
                    "away": teamA,
                    "pick": pick,
                    "confidence": confidence,
                    "odds": odds,
                    "all_odds": all_odds,
                    "league": league_name
                }
                
                all_matches.append(match_data)
                
                log(f"[MATCH] {teamH} vs {teamA} → {confidence}/10 → {pick} (cote: {odds})")
                
            except KeyError as e:
                log(f"[ERROR] Données manquantes pour un match: {e}")
                continue
            except Exception as e:
                log(f"[ERROR] Erreur traitement match: {e}")
                continue
    
    # Sort by confidence
    all_matches.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Select medium bets (top confidence)
    medium_bets = [m for m in all_matches if m["confidence"] >= 6.5][:3]
    
    # Select risk bets (next best, with diversity)
    medium_match_ids = [(m["home"], m["away"]) for m in medium_bets]
    remaining = [m for m in all_matches 
                if (m["home"], m["away"]) not in medium_match_ids 
                and m["confidence"] >= 5.0]
    risk_bets = remaining[:5]
    
    # Ensure prediction diversity in risk bets
    risk_bets = diversify_predictions(risk_bets)
    
    # Send messages
    if medium_bets:
        send_telegram(format_improved_combo("🔵 COMBINÉ SÉCURISÉ", medium_bets, "MEDIUM"))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic sécurisé aujourd'hui (confiance < 6.5/10)</b>")
    
    if risk_bets:
        send_telegram(format_improved_combo("🔴 COMBINÉ RISK (DIVERSIFIÉ)", risk_bets, "RISK"))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic risk aujourd'hui (confiance < 5.0/10)</b>")
    
    # Send statistics
    if all_matches:
        avg_confidence = statistics.mean([m["confidence"] for m in all_matches])
    else:
        avg_confidence = 0
    
    stats_msg = (
        f"📊 <b>STATISTIQUES DU JOUR</b>\n"
        f"├ Matchs analysés: {len(all_matches)}\n"
        f"├ Pronostics sécurisés: {len(medium_bets)}\n"
        f"├ Pronostics risk: {len(risk_bets)}\n"
        f"└ Fiabilité moyenne: {avg_confidence:.1f}/10"
    )
    send_telegram(stats_msg)
    
    log(f"✅ Terminé: {len(medium_bets)} MEDIUM, {len(risk_bets)} RISK")

if __name__ == "__main__":
    main()