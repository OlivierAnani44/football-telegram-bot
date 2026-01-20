import os
import requests
from understatapi import UnderstatClient

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

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
    else:
        print("Message envoyé:", msg[:50], "...")

def main():
    season = "2024"  # Saison passée La Liga 2024/25

    with UnderstatClient() as client:
        league = client.league("La_Liga")
        matches = league.get_match_data(season=season)

        if not matches:
            print(f"Aucun match récupéré pour la saison {season}")
            return

        print(f"{len(matches)} matchs récupérés pour La Liga {season}\n")

        for match in matches[:10]:  # Exemple : 10 premiers matchs
            home = match["h"]["title"]
            away = match["a"]["title"]
            goals_home = match.get("goals", {}).get("h", "-")
            goals_away = match.get("goals", {}).get("a", "-")
            xG_home = float(match.get("xG", {}).get("h", 0))
            xG_away = float(match.get("xG", {}).get("a", 0))

            # Vérifie la présence de shots et possession
            shots_home = int(match.get("shots", {}).get("h", 0))
            shots_away = int(match.get("shots", {}).get("a", 0))
            possession_home = float(match.get("possession", {}).get("h", 0))
            possession_away = float(match.get("possession", {}).get("a", 0))

            date_utc = match.get("datetime", "N/A")

            msg = (
                f"⚽ <b>{home} vs {away}</b>\n"
                f"Date UTC: {date_utc}\n"
                f"Score: {goals_home}-{goals_away} | xG: {xG_home:.2f}-{xG_away:.2f}\n"
                f"Tirs: {shots_home}-{shots_away} | Possession: {possession_home:.1f}% - {possession_away:.1f}%"
            )

            send_to_telegram(msg)

if __name__ == "__main__":
    main()
