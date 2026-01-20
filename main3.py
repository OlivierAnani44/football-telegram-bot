import requests
import datetime
import math

# ================= CONFIG =================

BOT_TOKEN = "TON_BOT_TOKEN"
CHANNEL_ID = "TON_CHANNEL_ID"

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

MIN_CONFIDENCE = 6        # filtre bookmaker
MAX_COMBINED = 5          # nombre max de matchs dans le combiné

# ==========================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHANNEL_ID,
        "text": message
    })

def get_matches_today(league):
    today = datetime.date.today().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={today}"
    try:
        return requests.get(url, timeout=10).json().get("events", [])
    except:
        return []

def get_team_form(team_id, league):
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team_id}/schedule"
    wins = draws = losses = gf = ga = 0

    try:
        data = requests.get(url, timeout=10).json()
        for e in data.get("events", [])[:5]:
            comp = e["competitions"][0]["competitors"]
            h, a = comp[0], comp[1]

            if h["id"] == team_id:
                sf, sa = int(h.get("score", 0)), int(a.get("score", 0))
            else:
                sf, sa = int(a.get("score", 0)), int(h.get("score", 0))

            gf += sf
            ga += sa

            if sf > sa:
                wins += 1
            elif sf < sa:
                losses += 1
            else:
                draws += 1
    except:
        pass

    return {
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "gf": gf,
        "ga": ga
    }

def compute_power(form, home=False):
    score = (
        form["wins"] * 3 +
        form["draws"] +
        (form["gf"] - form["ga"]) * 0.4
    )
    if home:
        score += 0.5
    return score

def predict_match(teamH, teamA, formH, formA):
    sH = compute_power(formH, home=True)
    sA = compute_power(formA)

    diff = sH - sA
    confidence = min(10, max(1, abs(diff)))

    if diff > 1:
        pick = f"{teamH} gagne"
    elif diff < -1:
        pick = f"{teamA} gagne"
    else:
        pick = "Match nul"

    probability = confidence / 10
    odds = round(1 / probability, 2)

    return pick, confidence, odds

# ================== MAIN ==================

combined_bets = []
combined_odds = 1.0

for league in LEAGUES:
    matches = get_matches_today(league)

    for match in matches:
        comp = match["competitions"][0]
        home, away = comp["competitors"]

        teamH = home["team"]["displayName"]
        teamA = away["team"]["displayName"]

        formH = get_team_form(home["team"]["id"], league)
        formA = get_team_form(away["team"]["id"], league)

        pick, confidence, odds = predict_match(teamH, teamA, formH, formA)

        if confidence < MIN_CONFIDENCE:
            continue

        combined_bets.append({
            "league": league,
            "match": f"{teamH} vs {teamA}",
            "pick": pick,
            "confidence": confidence,
            "odds": odds
        })

        combined_odds *= odds

        if len(combined_bets) >= MAX_COMBINED:
            break

    if len(combined_bets) >= MAX_COMBINED:
        break

# ================= MESSAGE =================

if not combined_bets:
    send_telegram("❌ Aucun match fiable trouvé aujourd'hui.")
else:
    msg = "🔥 MULTI-PRONOSTIC PREMIUM 🔥\n\n"
    for i, b in enumerate(combined_bets, 1):
        msg += (
            f"{i}️⃣ {b['match']}\n"
            f"➡️ {b['pick']}\n"
            f"🎯 Confiance : {b['confidence']}/10\n"
            f"💰 Cote : {b['odds']}\n\n"
        )

    msg += f"📊 COTE TOTALE COMBINÉE : {round(combined_odds, 2)}\n"
    msg += "⚠️ Mise responsable – Analyse IA\n"

    send_telegram(msg)
