import os
import requests
import datetime

# =============================
# VARIABLES ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =============================
# CONFIG
# =============================
UNDERSTAT_URL = "https://understat.com/league/La_liga/2025"  # Remplace par saison actuelle
MAX_MATCHES = 5  # Nombre de matchs à poster

# =============================
# FONCTION : Récupérer stats Understat
# =============================
def fetch_understat():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get(UNDERSTAT_URL, headers=headers)
    if r.status_code != 200:
        print("Erreur Understat:", r.status_code)
        return []

    # Les données Understat sont dans le script de la page
    import re, json
    data_match = re.search(r"var matchesData = JSON.parse\('(.+)'\);", r.text)
    if not data_match:
        print("Impossible de trouver les données JSON Understat")
        return []

    json_text = data_match.group(1)
    json_text = json_text.encode('utf-8').decode('unicode_escape')
    matches = json.loads(json_text)
    return matches[:MAX_MATCHES]

# =============================
# FONCTION : Poster sur Telegram
# =============================
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("Erreur Telegram:", r.text)
    else:
        print("Message envoyé:", message[:50], "...")

# =============================
# FONCTION : Générer message
# =============================
def generate_message(match):
    dt = datetime.datetime.fromtimestamp(int(match['datetime']))
    home = match['h']['title']
    away = match['a']['title']
    xG_home = float(match['xG']['h'])
    xG_away = float(match['xG']['a'])
    goals_home = match['goals']['h']
    goals_away = match['goals']['a']

    msg = (
        f"⚽ <b>{home} vs {away}</b>\n"
        f"Date UTC: {dt.strftime('%Y-%m-%d %H:%M')}\n"
        f"Score: {goals_home}-{goals_away}\n"
        f"xG: {xG_home:.2f}-{xG_away:.2f}"
    )
    return msg

# =============================
# PROGRAMME PRINCIPAL
# =============================
def main():
    matches = fetch_understat()
    if not matches:
        print("Aucun match récupéré")
        return

    for match in matches:
        msg = generate_message(match)
        send_to_telegram(msg)

if __name__ == "__main__":
    main()
