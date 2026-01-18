import os
import asyncio
import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Ton token Telegram
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Ton canal Telegram @nom_du_canal ou ID
FOOTBALL_URL = "https://www.livescore.com/fr/football/"  # Exemple pour récupérer matchs
CHECK_INTERVAL = 3600  # Vérifie toutes les heures (3600 sec)

# ================= FONCTIONS =================
async def fetch_matches():
    """Récupère les matchs du jour depuis le site"""
    async with aiohttp.ClientSession() as session:
        async with session.get(FOOTBALL_URL) as resp:
            if resp.status != 200:
                print("Erreur lors de la récupération des matchs")
                return []
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            matches = []
            # Exemple de parsing : tu devras adapter selon la structure du site
            for match in soup.find_all('div', class_='match-row'):
                teams = match.find_all('span', class_='team-name')
                score = match.find('span', class_='score')
                if teams:
                    home = teams[0].text.strip()
                    away = teams[1].text.strip() if len(teams) > 1 else ""
                    result = score.text.strip() if score else "vs"
                    matches.append(f"{home} {result} {away}")
            return matches

async def post_matches(bot):
    matches = await fetch_matches()
    if not matches:
        print("Aucun match trouvé pour aujourd'hui")
        return
    message = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    message += "\n".join(matches)
    
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=message)
        print("Message posté avec succès !")
    except Exception as e:
        print(f"Erreur lors de l'envoi sur Telegram: {e}")

async def main():
    bot = Bot(token=BOT_TOKEN)
    while True:
        await post_matches(bot)
        await asyncio.sleep(CHECK_INTERVAL)

# ================= EXECUTION =================
if __name__ == "__main__":
    asyncio.run(main())
