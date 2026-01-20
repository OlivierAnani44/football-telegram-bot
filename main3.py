import requests
import datetime
import os
import sys
import statistics
import json
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ANALYSIS_API_URL = os.getenv("ANALYSIS_API_URL", "http://localhost:8000/analyze")

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

# ================= DATA CLASSES =================
@dataclass
class TeamForm:
    wins: int
    draws: int
    losses: int
    gf: int  # goals for
    ga: int  # goals against
    matches_analyzed: int
    
    @property
    def win_rate(self) -> float:
        if self.matches_analyzed == 0:
            return 0.33
        return self.wins / self.matches_analyzed
    
    @property
    def goal_difference(self) -> int:
        return self.gf - self.ga
    
    @property
    def avg_goals_for(self) -> float:
        if self.matches_analyzed == 0:
            return 1.5
        return self.gf / self.matches_analyzed
    
    @property
    def avg_goals_against(self) -> float:
        if self.matches_analyzed == 0:
            return 1.5
        return self.ga / self.matches_analyzed

@dataclass
class MatchPrediction:
    home_team: str
    away_team: str
    prediction: str  # "home_win", "draw", "away_win"
    confidence: float  # 0-10
    odds: float
    all_odds: Dict[str, float]
    league: str
    analysis: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "home": self.home_team,
            "away": self.away_team,
            "pick": self.get_pick_text(),
            "confidence": self.confidence,
            "odds": self.odds,
            "all_odds": self.all_odds,
            "league": self.league,
            "analysis": self.analysis
        }
    
    def get_pick_text(self) -> str:
        if self.prediction == "home_win":
            return f"{self.home_team} gagne"
        elif self.prediction == "away_win":
            return f"{self.away_team} gagne"
        else:
            return "Match nul"

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

def get_team_form(team_id: str, league: str) -> TeamForm:
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
            return TeamForm(0, 0, 0, 0, 0, 0)
        
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
    
    return TeamForm(wins, draws, losses, gf, ga, matches_analyzed)

# ================= ANALYSIS API =================
def analyze_match_with_ai(
    home_team: str,
    away_team: str,
    home_form: TeamForm,
    away_form: TeamForm,
    league: str,
    is_home_big_team: bool,
    is_away_big_team: bool
) -> Dict[str, Any]:
    """
    Analyse un match en utilisant l'API d'analyse IA
    """
    # Préparer les données pour l'API
    match_data = {
        "home_team": home_team,
        "away_team": away_team,
        "home_form": {
            "wins": home_form.wins,
            "draws": home_form.draws,
            "losses": home_form.losses,
            "goals_for": home_form.gf,
            "goals_against": home_form.ga,
            "matches_analyzed": home_form.matches_analyzed,
            "win_rate": home_form.win_rate,
            "avg_goals_for": home_form.avg_goals_for,
            "avg_goals_against": home_form.avg_goals_against,
            "goal_difference": home_form.goal_difference
        },
        "away_form": {
            "wins": away_form.wins,
            "draws": away_form.draws,
            "losses": away_form.losses,
            "goals_for": away_form.gf,
            "goals_against": away_form.ga,
            "matches_analyzed": away_form.matches_analyzed,
            "win_rate": away_form.win_rate,
            "avg_goals_for": away_form.avg_goals_for,
            "avg_goals_against": away_form.avg_goals_against,
            "goal_difference": away_form.goal_difference
        },
        "league": league,
        "context": {
            "is_home_big_team": is_home_big_team,
            "is_away_big_team": is_away_big_team,
            "home_advantage": True,
            "is_champions_league": "champions" in league,
            "match_date": datetime.date.today().isoformat()
        }
    }
    
    try:
        # Appeler l'API d'analyse
        response = requests.post(
            ANALYSIS_API_URL,
            json=match_data,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            log(f"[WARN] API d'analyse retourne {response.status_code}: {response.text}")
            # Fallback: utiliser l'analyse locale
            return analyze_match_locally(match_data)
            
    except requests.exceptions.RequestException as e:
        log(f"[WARN] Erreur API d'analyse: {e}")
        # Fallback: utiliser l'analyse locale
        return analyze_match_locally(match_data)

def analyze_match_locally(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse locale en fallback si l'API n'est pas disponible
    """
    home_form = match_data["home_form"]
    away_form = match_data["away_form"]
    context = match_data["context"]
    
    # Calcul des probabilités de base
    home_strength = (
        home_form["win_rate"] * 3 +
        (home_form["avg_goals_for"] - home_form["avg_goals_against"]) * 0.2
    )
    away_strength = (
        away_form["win_rate"] * 3 +
        (away_form["avg_goals_for"] - away_form["avg_goals_against"]) * 0.2
    )
    
    # Avantage domicile
    home_advantage = 0.3 if context["home_advantage"] else 0
    
    # Bonus pour les grosses équipes
    home_big_team_bonus = 0.4 if context["is_home_big_team"] else 0
    away_big_team_bonus = 0.4 if context["is_away_big_team"] else 0
    
    # Calcul final des forces
    total_home_strength = home_strength + home_advantage + home_big_team_bonus
    total_away_strength = away_strength + away_big_team_bonus
    
    # Calcul des probabilités
    total = total_home_strength + total_away_strength + 1.0  # +1 pour le nul
    
    prob_home_win = total_home_strength / (total + 2)
    prob_away_win = total_away_strength / (total + 2)
    prob_draw = 1.0 / (total + 2)
    
    # Ajustement pour la Ligue des Champions
    if context["is_champions_league"]:
        prob_draw *= 0.8  # Moins de nuls en Champions
        prob_home_win *= 1.1
        prob_away_win *= 1.1
    
    # Normalisation
    total_prob = prob_home_win + prob_draw + prob_away_win
    prob_home_win /= total_prob
    prob_draw /= total_prob
    prob_away_win /= total_prob
    
    # Déterminer le pronostic
    if prob_home_win > prob_away_win and prob_home_win > prob_draw:
        prediction = "home_win"
        confidence = prob_home_win * 10
    elif prob_away_win > prob_home_win and prob_away_win > prob_draw:
        prediction = "away_win"
        confidence = prob_away_win * 10
    else:
        prediction = "draw"
        confidence = prob_draw * 10
    
    # Calcul des cotes avec marge
    margin = 1.05  # 5% de marge
    odds_home = round(margin / prob_home_win, 2) if prob_home_win > 0 else 100
    odds_draw = round(margin / prob_draw, 2) if prob_draw > 0 else 100
    odds_away = round(margin / prob_away_win, 2) if prob_away_win > 0 else 100
    
    # Limiter les cotes
    odds_home = max(1.5, min(20, odds_home))
    odds_draw = max(1.5, min(20, odds_draw))
    odds_away = max(1.5, min(20, odds_away))
    
    return {
        "prediction": prediction,
        "confidence": round(confidence, 2),
        "probabilities": {
            "home_win": round(prob_home_win, 3),
            "draw": round(prob_draw, 3),
            "away_win": round(prob_away_win, 3)
        },
        "odds": {
            "home_win": odds_home,
            "draw": odds_draw,
            "away_win": odds_away
        },
        "analysis": {
            "home_strength": round(total_home_strength, 2),
            "away_strength": round(total_away_strength, 2),
            "home_advantage": home_advantage,
            "big_team_bonus": {
                "home": home_big_team_bonus,
                "away": away_big_team_bonus
            },
            "matchup_balance": "Équilibré" if abs(total_home_strength - total_away_strength) < 0.5 else "Déséquilibré"
        },
        "source": "local_fallback"
    }

def predict_match_with_ai(
    home_team: str,
    away_team: str,
    home_form: TeamForm,
    away_form: TeamForm,
    league: str
) -> MatchPrediction:
    """
    Prédire le résultat d'un match en utilisant l'analyse IA
    """
    is_home_big_team = home_team in BIG_TEAMS
    is_away_big_team = away_team in BIG_TEAMS
    
    # Analyser le match avec l'API IA
    analysis_result = analyze_match_with_ai(
        home_team, away_team, home_form, away_form,
        league, is_home_big_team, is_away_big_team
    )
    
    # Extraire la ligue en format lisible
    league_parts = league.split(".")
    if len(league_parts) > 1:
        league_name = league_parts[0].upper()
    else:
        league_name = league.upper()
    
    # Créer la prédiction
    prediction = analysis_result["prediction"]
    confidence = analysis_result["confidence"]
    odds_dict = analysis_result["odds"]
    
    # Sélectionner la cote correspondante
    if prediction == "home_win":
        odds = odds_dict["home_win"]
    elif prediction == "away_win":
        odds = odds_dict["away_win"]
    else:
        odds = odds_dict["draw"]
    
    return MatchPrediction(
        home_team=home_team,
        away_team=away_team,
        prediction=prediction,
        confidence=confidence,
        odds=odds,
        all_odds=odds_dict,
        league=league_name,
        analysis=analysis_result.get("analysis", {})
    )

# ================= DIVERSIFICATION =================
def diversify_predictions(matches: List[MatchPrediction]) -> List[MatchPrediction]:
    """Ensure prediction diversity in the combo"""
    
    if len(matches) < 3:
        return matches
    
    # Convertir en dict pour manipulation
    match_dicts = [m.to_dict() for m in matches]
    
    # Count outcome types
    outcome_counts = {"home_wins": 0, "draws": 0, "away_wins": 0}
    
    for match in match_dicts:
        if "gagne" in match["pick"]:
            if match["home"] in match["pick"]:
                outcome_counts["home_wins"] += 1
            else:
                outcome_counts["away_wins"] += 1
        else:
            outcome_counts["draws"] += 1
    
    # If too many draws, diversify
    max_draws = max(2, len(match_dicts) // 3)  # Max 33% draws
    
    if outcome_counts["draws"] > max_draws:
        sorted_matches = sorted(match_dicts, key=lambda x: x["confidence"], reverse=True)
        
        # Replace some draws with other outcomes
        for match in sorted_matches:
            if outcome_counts["draws"] <= max_draws:
                break
                
            if "Match nul" in match["pick"]:
                # Get alternative odds for this match
                odds = match.get("all_odds", {})
                # Choose the next best outcome
                if odds.get("home_win", 2.0) <= odds.get("away_win", 2.0):
                    new_pick = f"{match['home']} gagne"
                    new_odds = odds.get("home_win", 2.0)
                    new_prediction = "home_win"
                else:
                    new_pick = f"{match['away']} gagne"
                    new_odds = odds.get("away_win", 2.0)
                    new_prediction = "away_win"
                
                # Update match
                match["pick"] = new_pick
                match["odds"] = new_odds
                match["confidence"] = match["confidence"] * 0.9  # Slightly reduce confidence
                
                outcome_counts["draws"] -= 1
                
                if new_prediction == "home_win":
                    outcome_counts["home_wins"] += 1
                else:
                    outcome_counts["away_wins"] += 1
    
    # Convertir de nouveau en MatchPrediction
    diversified_matches = []
    for match_dict in match_dicts:
        prediction = MatchPrediction(
            home_team=match_dict["home"],
            away_team=match_dict["away"],
            prediction="home_win" if match_dict["home"] in match_dict["pick"] else 
                      "away_win" if match_dict["away"] in match_dict["pick"] else "draw",
            confidence=match_dict["confidence"],
            odds=match_dict["odds"],
            all_odds=match_dict["all_odds"],
            league=match_dict["league"],
            analysis=match_dict.get("analysis", {})
        )
        diversified_matches.append(prediction)
    
    return diversified_matches

# ================= FORMATTING =================
def format_combo_message(title: str, predictions: List[MatchPrediction], risk_level: str) -> str:
    """Format combo message for Telegram"""
    if not predictions:
        return f"<b>{title}</b>\n\nAucun pronostic {risk_level} sélectionné aujourd'hui."
    
    message = f"<b>{title}</b>\n"
    message += f"📅 Date: {datetime.date.today().strftime('%d/%m/%Y')}\n"
    message += f"🎯 Fiabilité: {'Élevée' if risk_level == 'MEDIUM' else 'Modérée'}\n\n"
    
    total_odds = 1.0
    
    for i, pred in enumerate(predictions, 1):
        total_odds *= pred.odds
        
        # Determine emoji based on prediction type
        if pred.prediction == "draw":
            outcome_emoji = "⚖️"
        elif pred.prediction == "home_win":
            outcome_emoji = "🏠"
        else:
            outcome_emoji = "✈️"
        
        # Confidence indicator
        confidence_int = int(pred.confidence)
        conf_bars = "★" * min(5, confidence_int // 2) + "☆" * (5 - min(5, confidence_int // 2))
        
        # Analysis insights
        analysis_insight = ""
        if pred.analysis:
            if pred.analysis.get("matchup_balance") == "Déséquilibré":
                analysis_insight = " ⚡ Match déséquilibré"
            elif "home_advantage" in pred.analysis and pred.analysis["home_advantage"] > 0:
                analysis_insight = " 🏟️ Avantage domicile"
        
        message += (
            f"{i}. <b>{pred.home_team} vs {pred.away_team}</b>\n"
            f"   {outcome_emoji} <b>{pred.get_pick_text()}</b>{analysis_insight}\n"
            f"   🏆 {pred.league} | 📊 {conf_bars} ({pred.confidence:.1f}/10)\n"
            f"   💰 Cote: <b>{pred.odds}</b>\n\n"
        )
    
    # Calculate realistic stake
    if risk_level == "MEDIUM":
        recommended_stake = min(10, max(1, round(15 / total_odds, 2)))
    else:
        recommended_stake = min(5, max(0.5, round(8 / total_odds, 2)))
    
    potential_win = round(recommended_stake * total_odds, 2)
    
    message += (
        f"📈 <b>RÉSUMÉ DU COMBINÉ</b>\n"
        f"├ Nombre de matchs: {len(predictions)}\n"
        f"├ Cote totale: <b>{round(total_odds, 2)}</b>\n"
        f"├ Mise recommandée: <b>{recommended_stake}€</b>\n"
        f"└ Gain potentiel: <b>{potential_win}€</b>\n\n"
        f"<i>⚠️ Les paris sportifs comportent des risques</i>"
    )
    
    return message

# ================= MAIN =================
def main():
    log("🚀 Bot de pronostics avec analyse IA démarré")
    send_telegram("✅ <b>Bot pronostics avec IA actif</b>")
    
    medium_predictions = []
    risk_predictions = []
    all_predictions = []
    
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
                
                home_team = h.get("team", {}).get("displayName", "Inconnu")
                away_team = a.get("team", {}).get("displayName", "Inconnu")
                home_id = h.get("team", {}).get("id")
                away_id = a.get("team", {}).get("id")
                
                if not home_id or not away_id:
                    log(f"[SKIP] {home_team} vs {away_team} - IDs manquants")
                    continue
                
                # Skip if match already started or finished
                status = match.get("status", {})
                status_type = status.get("type", {})
                if status_type.get("id") != "1":  # 1 = scheduled
                    log(f"[SKIP] {home_team} vs {away_team} - Match déjà commencé ou terminé")
                    continue
                
                # Get team forms
                home_form = get_team_form(home_id, league)
                away_form = get_team_form(away_id, league)
                
                # Make prediction with AI analysis
                prediction = predict_match_with_ai(
                    home_team, away_team, home_form, away_form, league
                )
                
                all_predictions.append(prediction)
                
                log(f"[MATCH] {home_team} vs {away_team} → {prediction.confidence:.1f}/10 → {prediction.get_pick_text()} (cote: {prediction.odds})")
                
            except KeyError as e:
                log(f"[ERROR] Données manquantes pour un match: {e}")
                continue
            except Exception as e:
                log(f"[ERROR] Erreur traitement match: {e}")
                continue
    
    # Sort by confidence
    all_predictions.sort(key=lambda x: x.confidence, reverse=True)
    
    # Select medium predictions (top confidence)
    medium_predictions = [p for p in all_predictions if p.confidence >= 6.5][:3]
    
    # Select risk predictions (next best, with diversity)
    medium_match_ids = [(p.home_team, p.away_team) for p in medium_predictions]
    remaining = [p for p in all_predictions 
                if (p.home_team, p.away_team) not in medium_match_ids 
                and p.confidence >= 5.0]
    risk_predictions = remaining[:5]
    
    # Ensure prediction diversity in risk predictions
    risk_predictions = diversify_predictions(risk_predictions)
    
    # Send messages
    if medium_predictions:
        send_telegram(format_combo_message("🔵 COMBINÉ SÉCURISÉ (IA)", medium_predictions, "MEDIUM"))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic sécurisé aujourd'hui (confiance < 6.5/10)</b>")
    
    if risk_predictions:
        send_telegram(format_combo_message("🔴 COMBINÉ RISK (IA DIVERSIFIÉ)", risk_predictions, "RISK"))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic risk aujourd'hui (confiance < 5.0/10)</b>")
    
    # Send statistics
    if all_predictions:
        avg_confidence = statistics.mean([p.confidence for p in all_predictions])
        pred_source = "API IA" if ANALYSIS_API_URL != "http://localhost:8000/analyze" else "Fallback local"
    else:
        avg_confidence = 0
        pred_source = "Aucune"
    
    stats_msg = (
        f"📊 <b>STATISTIQUES DU JOUR</b>\n"
        f"├ Matchs analysés: {len(all_predictions)}\n"
        f"├ Pronostics sécurisés: {len(medium_predictions)}\n"
        f"├ Pronostics risk: {len(risk_predictions)}\n"
        f"├ Fiabilité moyenne: {avg_confidence:.1f}/10\n"
        f"└ Source analyse: {pred_source}"
    )
    send_telegram(stats_msg)
    
    log(f"✅ Terminé: {len(medium_predictions)} MEDIUM, {len(risk_predictions)} RISK")
    log(f"📡 API utilisée: {ANALYSIS_API_URL}")

if __name__ == "__main__":
    main()