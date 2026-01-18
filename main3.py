import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SCOREBAT_API = "https://www.scorebat.com/video-api/v3/"

async def fetch_matches():
    async with aiohttp.ClientSession() as session:
        async with session.get(SCOREBAT_API) as resp:
            data = await resp.json()
            matches = []
            for match in data.get("response", []):
                # Vérifie que c'est bien un dictionnaire
                if isinstance(match, dict):
                    title = match.get("title", "Match inconnu")
                    competition = match.get("competition", {}).get("name", "Compétition inconnue")
                    date = match.get("date", "")
                    matches.append(f"{title} - {competition} ({date})")
                else:
                    # Si c'est une string ou autre type, on l'ignore
                    continue
            return matches

async def main():
    bot = Bot(token=BOT_TOKEN)
    matches = await fetch_matches()
    if not matches:
        print("Aucun match trouvé aujourd'hui")
        return
    message = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    message += "\n".join(matches)
    
    # Telegram limite : 4096 caractères
    MAX_LEN = 4000
    messages = []
    current_msg = ""
    for line in message.split("\n"):
        if len(current_msg) + len(line) + 1 > MAX_LEN:
            messages.append(current_msg)
            current_msg = line
        else:
            current_msg += "\n" + line if current_msg else line
    if current_msg:
        messages.append(current_msg)

    # Envoi sur Telegram
    for msg in messages:
        await bot.send_message(chat_id=CHANNEL_ID, text=msg)
    print(f"{len(matches)} match(es) posté(s) sur Telegram !")

if __name__ == "__main__":
    asyncio.run(main())
