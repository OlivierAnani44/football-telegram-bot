import requests
import datetime
import os
import sys
import statistics
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from openai import OpenAI

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Vérification des variables d'environnement
print("DEBUG BOT_TOKEN:", "OK" if BOT_TOKEN else "MANQUANT")
print("DEBUG CHANNEL_ID:", "OK" if CHANNEL_ID else "MANQUANT")
print("DEBUG DEEPSEEK_API_KEY:", "OK" if DEEPSEEK_API_KEY else "MANQUANT")

if not BOT_TOKEN or not CHANNEL_ID or not DEEPSEEK_API_KEY:
    print("❌ Variables BOT_TOKEN, CHANNEL_ID ou DEEPSEEK_API_KEY manquantes")
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
    gf: int
    ga: int
    matches_analyzed: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "goals_for": self.gf,
            "goals_against": self.ga,
            "matches_analyzed": self.matches_analyzed
        }

@dataclass
class MatchPrediction:
    home_team: str
    away_team: str
    prediction: str
    confidence: float
    odds: float
    analysis_text: str
    league: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "home": self.home_team,
            "away": self.away_team,
            "pick": self.get_pick_text(),
            "confidence": self.confidence,
            "odds": self.odds,
            "analysis": self.analysis_text,
            "league": self.league
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
        
        for e in completed_matches[:5]:
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
            except Exception:
                continue
                
    except Exception as e:
        log(f"[WARN] Erreur get_team_form pour {team_id}: {e}")
    
    return TeamForm(wins, draws, losses, gf, ga, matches_analyzed)

# ================= DEEPSEEK ANALYSIS =================
def analyze_match_with_deepseek(
    home_team: str,
    away_team: str,
    home_form: TeamForm,
    away_form: TeamForm,
    league: str,
    is_home_big: bool,
    is_away_big: bool
) -> Tuple[str, float, str]:
    """Analyze match using DeepSeek API"""
    
    # Initialiser le client DeepSeek
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )
    
    # Préparer le prompt
    prompt = f"""
    Tu es un expert en analyse footballistique. Analyse ce match et donne:
    1. Un pronostic: "home_win", "away_win", ou "draw"
    2. Un score de confiance de 1 à 10 (10 étant le plus sûr)
    3. Une analyse courte en français (max 2 phrases)
    
    MATCH À ANALYSER:
    - Équipe domicile: {home_team} {'(Grosse équipe)' if is_home_big else ''}
    - Équipe extérieure: {away_team} {'(Grosse équipe)' if is_away_big else ''}
    - Ligue: {league}
    
    FORME RÉCENTE (5 derniers matchs):
    {home_team}: {home_form.wins}V, {home_form.draws}N, {home_form.losses}D. Buts: {home_form.gf} pour, {home_form.ga} contre.
    {away_team}: {away_form.wins}V, {away_form.draws}N, {away_form.losses}D. Buts: {away_form.gf} pour, {away_form.ga} contre.
    
    Considère:
    - L'avantage domicile
    - La forme récente
    - La différence de buts
    - Le statut de "grosse équipe"
    - Le type de ligue
    
    Réponds EXACTEMENT dans ce format:
    PRONOSTIC: [home_win/away_win/draw]
    CONFIDENCE: [nombre de 1 à 10]
    ANALYSE: [ton analyse en français]
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Tu es un analyste footballistique expert. Réponds toujours dans le format demandé."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parser la réponse
        lines = result_text.split('\n')
        prediction = ""
        confidence = 5.0
        analysis = "Analyse non disponible"
        
        for line in lines:
            if line.startswith("PRONOSTIC:"):
                prediction = line.replace("PRONOSTIC:", "").strip().lower()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                    confidence = max(1.0, min(10.0, confidence))
                except:
                    confidence = 5.0
            elif line.startswith("ANALYSE:"):
                analysis = line.replace("ANALYSE:", "").strip()
        
        return prediction, confidence, analysis
        
    except Exception as e:
        log(f"[ERROR DEEPSEEK] {e}")
        # Fallback en cas d'erreur
        return "draw", 5.0, "Erreur d'analyse avec l'IA"

def calculate_odds(prediction: str, confidence: float, home_big: bool, away_big: bool) -> float:
    """Calculate odds based on prediction and confidence"""
    base_odds = 10.0 / confidence
    
    # Ajustements
    if prediction == "home_win" and home_big:
        base_odds *= 0.8
    elif prediction == "away_win" and away_big:
        base_odds *= 0.8
    elif prediction == "draw":
        base_odds *= 1.2
    
    # Assurer des cotes réalistes
    odds = max(1.5, min(10.0, round(base_odds, 2)))
    return odds

def predict_match(
    home_team: str,
    away_team: str,
    home_form: TeamForm,
    away_form: TeamForm,
    league: str
) -> MatchPrediction:
    """Create match prediction using DeepSeek"""
    
    is_home_big = home_team in BIG_TEAMS
    is_away_big = away_team in BIG_TEAMS
    
    # Analyser avec DeepSeek
    prediction, confidence, analysis = analyze_match_with_deepseek(
        home_team, away_team, home_form, away_form,
        league, is_home_big, is_away_big
    )
    
    # Calculer les cotes
    odds = calculate_odds(prediction, confidence, is_home_big, is_away_big)
    
    # Format de la ligue
    league_parts = league.split(".")
    if len(league_parts) > 1:
        league_name = league_parts[0].upper()
    else:
        league_name = league.upper()
    
    return MatchPrediction(
        home_team=home_team,
        away_team=away_team,
        prediction=prediction,
        confidence=confidence,
        odds=odds,
        analysis_text=analysis,
        league=league_name
    )

# ================= DIVERSIFICATION =================
def diversify_predictions(predictions: List[MatchPrediction]) -> List[MatchPrediction]:
    """Ensure we don't have too many draws"""
    if len(predictions) < 3:
        return predictions
    
    draw_count = sum(1 for p in predictions if p.prediction == "draw")
    max_draws = max(1, len(predictions) // 3)
    
    if draw_count <= max_draws:
        return predictions
    
    # Convertir quelques nuls en victoires
    sorted_preds = sorted(predictions, key=lambda x: x.confidence, reverse=True)
    for i, pred in enumerate(sorted_preds):
        if pred.prediction == "draw" and draw_count > max_draws:
            # Changer en victoire domicile (simplifié)
            pred.prediction = "home_win"
            pred.confidence *= 0.9  # Réduire légèrement la confiance
            pred.odds = calculate_odds("home_win", pred.confidence, 
                                      pred.home_team in BIG_TEAMS, 
                                      pred.away_team in BIG_TEAMS)
            draw_count -= 1
        
        if draw_count <= max_draws:
            break
    
    return sorted_preds

# ================= FORMATTING =================
def format_combo_message(title: str, predictions: List[MatchPrediction], risk_level: str) -> str:
    """Format combo message for Telegram"""
    if not predictions:
        return f"<b>{title}</b>\n\nAucun pronostic {risk_level} aujourd'hui."
    
    message = f"<b>{title}</b>\n"
    message += f"📅 {datetime.date.today().strftime('%d/%m/%Y')}\n"
    message += f"🤖 Analyse par IA DeepSeek\n\n"
    
    total_odds = 1.0
    
    for i, pred in enumerate(predictions, 1):
        total_odds *= pred.odds
        
        # Emoji selon le pronostic
        if pred.prediction == "draw":
            outcome_emoji = "⚖️"
        elif pred.prediction == "home_win":
            outcome_emoji = "🏠"
        else:
            outcome_emoji = "✈️"
        
        # Étoiles de confiance
        stars = min(5, int(pred.confidence / 2))
        conf_bars = "★" * stars + "☆" * (5 - stars)
        
        message += (
            f"{i}. <b>{pred.home_team} vs {pred.away_team}</b>\n"
            f"   {outcome_emoji} <b>{pred.get_pick_text()}</b>\n"
            f"   🏆 {pred.league} | 📊 {conf_bars} ({pred.confidence:.1f}/10)\n"
            f"   💰 Cote: <b>{pred.odds}</b>\n"
            f"   📝 {pred.analysis_text}\n\n"
        )
    
    # Calcul de la mise recommandée
    if risk_level == "MEDIUM":
        stake = min(10, max(2, round(20 / total_odds, 2)))
    else:
        stake = min(5, max(1, round(10 / total_odds, 2)))
    
    potential_win = round(stake * total_odds, 2)
    
    message += (
        f"📈 <b>RÉSUMÉ</b>\n"
        f"├ Matchs: {len(predictions)}\n"
        f"├ Cote totale: <b>{round(total_odds, 2)}</b>\n"
        f"├ Mise conseillée: <b>{stake}€</b>\n"
        f"└ Gain possible: <b>{potential_win}€</b>\n\n"
        f"<i>⚠️ Paris sportifs = risques. Jouez responsablement.</i>"
    )
    
    return message

# ================= MAIN =================
def main():
    log("🚀 Bot de pronostics avec DeepSeek IA démarré")
    send_telegram("🤖 <b>Bot Pronostics IA activé</b>\nAnalyse des matchs en cours...")
    
    all_predictions = []
    
    log("📊 Collecte des matchs du jour...")
    
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
                    continue
                
                # Vérifier si le match n'a pas encore commencé
                status = match.get("status", {}).get("type", {})
                if status.get("id") != "1":  # 1 = programmé
                    log(f"[SKIP] {home_team} vs {away_team} - Match déjà commencé")
                    continue
                
                # Obtenir les formes des équipes
                log(f"[ANALYSE] {home_team} vs {away_team}")
                home_form = get_team_form(home_id, league)
                away_form = get_team_form(away_id, league)
                
                # Générer la prédiction avec DeepSeek
                prediction = predict_match(home_team, away_team, home_form, away_form, league)
                all_predictions.append(prediction)
                
                log(f"[PRONO] {home_team} vs {away_team}: {prediction.get_pick_text()} ({prediction.confidence:.1f}/10)")
                
            except Exception as e:
                log(f"[ERROR] Traitement match: {e}")
                continue
    
    # Trier par confiance
    all_predictions.sort(key=lambda x: x.confidence, reverse=True)
    
    # Sélectionner les pronostics MEDIUM (meilleure confiance)
    medium_predictions = [p for p in all_predictions if p.confidence >= 6.5][:3]
    
    # Sélectionner les pronostics RISK (avec diversification)
    remaining = [p for p in all_predictions if p not in medium_predictions and p.confidence >= 5.0]
    risk_predictions = remaining[:5]
    risk_predictions = diversify_predictions(risk_predictions)
    
    # Envoyer les messages Telegram
    if medium_predictions:
        send_telegram(format_combo_message("🔵 COMBINÉ SÉCURISÉ", medium_predictions, "MEDIUM"))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic sécurisé aujourd'hui</b>\n(Confiance insuffisante: < 6.5/10)")
    
    if risk_predictions:
        send_telegram(format_combo_message("🔴 COMBINÉ RISK", risk_predictions, "RISK"))
    else:
        send_telegram("ℹ️ <b>Aucun pronostic risk aujourd'hui</b>\n(Confiance insuffisante: < 5.0/10)")
    
    # Statistiques
    if all_predictions:
        avg_conf = statistics.mean([p.confidence for p in all_predictions])
    else:
        avg_conf = 0
    
    stats_msg = (
        f"📊 <b>STATISTIQUES JOUR</b>\n"
        f"├ Matchs analysés: {len(all_predictions)}\n"
        f"├ Pronostics sécurisés: {len(medium_predictions)}\n"
        f"├ Pronostics risk: {len(risk_predictions)}\n"
        f"└ Confiance moyenne: {avg_conf:.1f}/10\n\n"
        f"🔍 Analyse par: DeepSeek AI"
    )
    send_telegram(stats_msg)
    
    log(f"✅ Terminé! {len(medium_predictions)} MEDIUM, {len(risk_predictions)} RISK")

if __name__ == "__main__":
    main()