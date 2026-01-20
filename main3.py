import requests
import datetime
import random
import statistics
from typing import List, Tuple, Dict

# -----------------------------
# CONFIGURATION
# -----------------------------
# Liste des "grands clubs" pour ajustement de réputation
BIG_TEAMS = [
    "Real Madrid", "Barcelona", "Manchester United", "Liverpool",
    "Bayern Munich", "Juventus", "Paris Saint-Germain", "Chelsea",
    "Manchester City", "Arsenal", "AC Milan", "Inter Milan"
]

# Ligues à surveiller
LEAGUES = [
    "premier_league",
    "laliga",
    "serie_a",
    "bundesliga",
    "ligue_1",
    "liga_portugal",
    "eredivisie",
    "champions_league"
]

# -----------------------------
# UTILITAIRES
# -----------------------------
def log(message: str):
    """Simple logger"""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}")

def send_telegram(message: str):
    """Placeholder pour l'envoi Telegram"""
    log(f"(Telegram) {message}")
    # Ici tu peux mettre requests.post vers ton bot Telegram API

def get_matches_today(league: str) -> List[Dict]:
    """Exemple simplifié pour récupérer des matchs aujourd'hui"""
    # Pour test, on retourne des matchs fictifs
    sample_matches = [
        {"home": "Real Madrid", "away": "Barcelona"},
        {"home": "Liverpool", "away": "Manchester United"},
        {"home": "Juventus", "away": "Inter Milan"},
    ]
    return sample_matches

# -----------------------------
# CALCUL DES CONFIANCES & ODDS
# -----------------------------
def calculate_confidence_score(formH: Dict, formA: Dict, teamH: str, teamA: str, league: str) -> Dict[str, float]:
    scores = {"home_win": 5.0, "draw": 5.0, "away_win": 5.0}

    # Forme récente (40%)
    if formH["matches_analyzed"] > 0 and formA["matches_analyzed"] > 0:
        home_strength = (formH["wins"] * 3 + formH["draws"]) / formH["matches_analyzed"]
        away_strength = (formA["wins"] * 3 + formA["draws"]) / formA["matches_analyzed"]
        form_diff = home_strength - away_strength
        scores["home_win"] += form_diff * 2.0
        scores["away_win"] -= form_diff * 2.0

    # Buts (30%)
    home_avg_gf = formH["gf"] / formH["matches_analyzed"] if formH["matches_analyzed"] > 0 else 1.5
    home_avg_ga = formH["ga"] / formH["matches_analyzed"] if formH["matches_analyzed"] > 0 else 1.5
    away_avg_gf = formA["gf"] / formA["matches_analyzed"] if formA["matches_analyzed"] > 0 else 1.5
    away_avg_ga = formA["ga"] / formA["matches_analyzed"] if formA["matches_analyzed"] > 0 else 1.5

    expected_home_goals = (home_avg_gf + away_avg_ga) / 2
    expected_away_goals = (away_avg_gf + home_avg_ga) / 2
    goal_diff = expected_home_goals - expected_away_goals
    scores["home_win"] += goal_diff * 0.5
    scores["away_win"] -= goal_diff * 0.5

    # Draw likelihood
    goal_proximity = 1.0 - min(1.0, abs(goal_diff) / 3.0)
    scores["draw"] += goal_proximity * 1.5

    # Avantage domicile (15%)
    scores["home_win"] += 1.2
    scores["draw"] += 0.4

    # Réputation équipes (10%)
    if teamH in BIG_TEAMS:
        scores["home_win"] += 1.5
        scores["draw"] += 0.3
    if teamA in BIG_TEAMS:
        scores["away_win"] += 1.5
        scores["draw"] += 0.3

    # Ajustement ligue (5%)
    if "champions" in league.lower():
        scores["draw"] -= 0.5

    # Normalisation
    for key in scores:
        scores[key] = max(1.0, min(10.0, scores[key]))
    return scores

def calculate_realistic_odds(confidence_scores: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, float]]:
    total = sum(confidence_scores.values())
    probabilities = {k: v / total for k, v in confidence_scores.items()}
    margin = 1.05
    odds = {k: round(margin / p, 2) for k, p in probabilities.items()}
    for k in odds:
        odds[k] = max(1.5, min(10, odds[k]))
    return odds, probabilities

def predict_match_v2(teamH: str, teamA: str, formH: Dict, formA: Dict, league: str) -> Tuple[str, float, float, Dict[str, float]]:
    confidence_scores = calculate_confidence_score(formH, formA, teamH, teamA, league)
    odds, probabilities = calculate_realistic_odds(confidence_scores)

    best_outcome = max(confidence_scores, key=confidence_scores.get)
    outcome_map = {"home_win": f"{teamH} gagne", "draw": "Match nul", "away_win": f"{teamA} gagne"}
    pick = outcome_map[best_outcome]

    composite_confidence = sum(confidence_scores[k] * probabilities[k] for k in confidence_scores)
    selected_odds = odds[best_outcome]
    return pick, round(composite_confidence, 1), selected_odds, odds

# -----------------------------
# DIVERSIFICATION DES PRONOS
# -----------------------------
def diversify_predictions(matches: List[Dict]) -> List[Dict]:
    if len(matches) < 3:
        return matches

    outcome_counts = {"home_wins": 0, "draws": 0, "away_wins": 0}
    for match in matches:
        if "gagne" in match["pick"]:
            if match["home"] in match["pick"]:
                outcome_counts["home_wins"] += 1
            else:
                outcome_counts["away_wins"] += 1
        else:
            outcome_counts["draws"] += 1

    max_draws = max(2, len(matches) // 3)
    if outcome_counts["draws"] > max_draws:
        sorted_matches = sorted(matches, key=lambda x: x["confidence"], reverse=True)
        for match in sorted_matches:
            if "Match nul" in match["pick"] and outcome_counts["draws"] > max_draws:
                odds = match["all_odds"]
                if odds["home_win"] <= odds["away_win"]:
                    new_pick = f"{match['home']} gagne"
                    new_odds = odds["home_win"]
                else:
                    new_pick = f"{match['away']} gagne"
                    new_odds = odds["away_win"]

                match["pick"] = new_pick
                match["odds"] = new_odds
                match["confidence"] *= 0.9

                outcome_counts["draws"] -= 1
                if new_pick == f"{match['home']} gagne":
                    outcome_counts["home_wins"] += 1
                else:
                    outcome_counts["away_wins"] += 1
                if outcome_counts["draws"] <= max_draws:
                    break
    return matches

# -----------------------------
# MAIN
# -----------------------------
def main():
    log("🚀 Bot de pronostics démarré (version complète)")
    send_telegram("✅ <b>Bot pronostics actif - Version complète</b>")

    all_matches = []
    for league in LEAGUES:
        events = get_matches_today(league)
        for match in events:
            teamH = match["home"]
            teamA = match["away"]
            # Forme fictive pour test
            formH = {"matches_analyzed": 8, "wins": random.randint(3, 6), "draws": random.randint(0, 3), "ga": random.randint(4, 10), "gf": random.randint(5, 12)}
            formA = {"matches_analyzed": 8, "wins": random.randint(2, 5), "draws": random.randint(0, 3), "ga": random.randint(5, 12), "gf": random.randint(4, 10)}

            pick, confidence, odds, all_odds = predict_match_v2(teamH, teamA, formH, formA, league)
            match_data = {
                "home": teamH,
                "away": teamA,
                "pick": pick,
                "confidence": confidence,
                "odds": odds,
                "all_odds": all_odds,
                "league": league.upper()
            }
            all_matches.append(match_data)
            log(f"[MATCH] {teamH} vs {teamA} → {confidence}/10 → {pick} (cote: {odds})")

    # Exemple de tri et envoi
    all_matches.sort(key=lambda x: x["confidence"], reverse=True)
    send_telegram(f"📊 {len(all_matches)} matchs analysés aujourd'hui.")

if __name__ == "__main__":
    main()
