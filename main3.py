import os
import requests
from understatapi import UnderstatClient

# =============================
# VARIABLES D'ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =============================
# FONCTION TELEGRAM
# =============================
def send_to_telegram(msg: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        print("Erreur Telegram:", response.text)

# =============================
# PROGRAMME PRINCIPAL
# =============================
def main():
    with UnderstatClient() as client:
        # 1️⃣ Récupère les matchs de La Liga (dernier match de la saison 2026)
        league = client.league("La_Liga")
        matches = league.get_match_data(season="2026")  # récupère tous les matchs de la saison

        if not matches:
            print("Aucun match récupéré")
            return

        # 2️⃣ On prend les 5 derniers matchs pour poster sur Telegram
        latest_matches = matches[-5:]  # les plus récents

        for match in latest_matches:
            # Extrait les infos utiles
            date_utc = match["datetime"]
            home_team = match["h"]["title"]
            away_team = match["a"]["title"]
            goals_home = match["goals"]["h"]
            goals_away = match["goals"]["a"]
            xG_home = float(match["xG"]["h"])
            xG_away = float(match["xG"]["a"])

            # Crée le message
            msg = (
                f"⚽ <b>{home_team} vs {away_team}</b>\n"
                f"Date UTC: {date_utc}\n"
                f"Score: {goals_home}-{goals_away}\n"
                f"xG: {xG_home:.2f}-{xG_away:.2f}"
            )

            # 3️⃣ Envoie sur Telegram
            send_to_telegram(msg)

if __name__ == "__main__":
    main()
