import requests
import datetime
import math
import sys

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

MIN_CONFIDENCE = 6
MAX_COMBINED = 5

# ==========================================

def log(msg):
    print(msg)
    sys.stdout.flush()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": CHANNEL_ID,
        "text": message
    })
    log(f"[TELEGRAM] status={r.status_code} response={r.text}")

def get_matches_today(league):
    today = datetime.date.today().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={today}"
    try:
        data = requests.get(url, timeout=10).json()
        events = data.get("events", [])
        log(f"[INFO] {league} → {len(events)} matchs trouvés")
        return events
    except Exception as e:
        log(f"[ERROR] {league} récupération échouée : {e}")
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

def compute_power(form, home=False):
    score = (
        form["wins"] * 3 +
        form["draws"] +
        (form["gf"] - form["ga"]) * 0.4
    )
    if home:
        score += 0.5
    return score

def predict(teamH, teamA, formH, formA):
    sH = compute_power(formH, home=True)
    sA = compute_power(formA)

    diff = sH - sA
    confidence = round(min(10, max(1, abs(diff))), 2)

    if diff > 1:
        pick = f"{teamH} gagne"
    elif diff < -1:
        pick = f"{teamA} gagne"
    else:
        pick = "Match nul"

    odds = round(1 / (confidence / 10), 2)
    return pick, confidence, odds

# ================= MAIN =================

log("🚀 Bot démarré")
send_telegram("✅ Bot pronostic lancé avec debug actif")

combined = []
total_odds = 1.0

for league in LEAGUES:
    matches = get_matches_today(league)

    for m in matches:
        comp = m["competitions"][0]
        h, a = comp["competitors"]

        teamH = h["team"]["displayName"]
        teamA = a["team"]["displayName"]

        formH = get_team_form(h["team"]["id"], league)
        formA = get_team_form(a["team"]["id"], league)

        pick, conf, odds = predict(teamH, teamA, formH, formA)

        log(f"[MATCH] {teamH} vs {teamA} → confiance {conf}")

        if conf < MIN_CONFIDENCE:
            log("⛔ rejeté (confiance insuffisante)")
            continue

        combined.append((teamH, teamA, pick, conf, odds))
        total_odds *= odds

        if len(combined) >= MAX_COMBINED:
            break

    if len(combined) >= MAX_COMBINED:
        break

log(f"[INFO] Matchs retenus : {len(combined)}")

if not combined:
    send_telegram("❌ Aucun match assez fiable aujourd’hui (debug OK).")
else:
    msg = "🔥 MULTI-PRONOSTIC PREMIUM 🔥\n\n"
    for i, c in enumerate(combined, 1):
        msg += (
            f"{i}️⃣ {c[0]} vs {c[1]}\n"
            f"➡️ {c[2]}\n"
            f"🎯 Confiance : {c[3]}/10\n"
            f"💰 Cote : {c[4]}\n\n"
        )

    msg += f"📊 COTE TOTALE : {round(total_odds, 2)}"
    send_telegram(msg)
