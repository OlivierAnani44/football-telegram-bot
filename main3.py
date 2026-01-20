import requests
import datetime
import os
import sys

# ================= ENV =================

BOT_TOKEN = os.getenv("BOT TOKEN")
CHANNEL_ID = os.getenv("CHANNEL ID")

if not BOT_TOKEN or not CHANNEL_ID:
    print("❌ Variables BOT TOKEN ou CHANNEL ID manquantes")
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

def log(msg):
    print(msg)
    sys.stdout.flush()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": CHANNEL_ID,
        "text": message
    })
    log(f"[TELEGRAM] {r.status_code} {r.text}")

def get_matches_today(league):
    today = datetime.date.today().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={today}"
    try:
        data = requests.get(url, timeout=10).json()
        events = data.get("events", [])
        log(f"[INFO] {league} → {len(events)} matchs")
        return events
    except Exception as e:
        log(f"[ERROR] {league} → {e}")
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

    return {"wins": wins, "draws": draws, "losses": losses, "gf": gf, "ga": ga}

def predict(teamH, teamA, formH, formA):
    score = 5

    score += (formH["wins"] - formA["wins"]) * 0.7
    score += ((formH["gf"] - formH["ga"]) - (formA["gf"] - formA["ga"])) * 0.3
    score += 0.8  # domicile

    if teamH in BIG_TEAMS:
        score += 0.7
    if teamA in BIG_TEAMS:
        score -= 0.7

    confidence = round(max(3, min(9, score)), 1)

    if confidence >= 6:
        pick = f"{teamH} gagne"
    elif confidence <= 4:
        pick = f"{teamA} gagne"
    else:
        pick = "Match nul"

    odds = round(1 / (confidence / 10), 2)
    return pick, confidence, odds

# ================= MAIN =================

log("🚀 Bot lancé")
send_telegram("✅ Bot pronostics actif")

medium = []
risk = []

for league in LEAGUES:
    for m in get_matches_today(league):
        comp = m["competitions"][0]
        h, a = comp["competitors"]

        teamH = h["team"]["displayName"]
        teamA = a["team"]["displayName"]

        formH = get_team_form(h["team"]["id"], league)
        formA = get_team_form(a["team"]["id"], league)

        pick, conf, odds = predict(teamH, teamA, formH, formA)

        log(f"[MATCH] {teamH} vs {teamA} → {conf}")

        if conf >= 6 and len(medium) < 3:
            medium.append((teamH, teamA, pick, conf, odds))

        if conf >= 5 and len(risk) < 5:
            risk.append((teamH, teamA, pick, conf, odds))

# ================= SEND =================

def send_combo(title, bets):
    if not bets:
        return

    total = 1
    msg = f"{title}\n\n"
    for i, b in enumerate(bets, 1):
        total *= b[4]
        msg += (
            f"{i}️⃣ {b[0]} vs {b[1]}\n"
            f"➡️ {b[2]}\n"
            f"🎯 Confiance : {b[3]}/10\n"
            f"💰 Cote : {b[4]}\n\n"
        )

    msg += f"📊 COTE TOTALE : {round(total, 2)}"
    send_telegram(msg)

send_combo("🔵 COMBINÉ MEDIUM", medium)
send_combo("🔴 COMBINÉ RISK", risk)
