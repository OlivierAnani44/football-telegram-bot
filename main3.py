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
                title = match.get("title")
                competition = match.get("competition", {}).get("name")
                date = match.get("date")
                matches.append(f"{title} - {competition} ({date})")
            return matches

async def main():
    bot = Bot(token=BOT_TOKEN)
    matches = await fetch_matches()
    if not matches:
        print("Aucun match trouvé aujourd'hui")
        return
    message = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    message += "\n".join(matches)
    await bot.send_message(chat_id=CHANNEL_ID, text=message)

if __name__ == "__main__":
    asyncio.run(main())
