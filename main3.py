import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SCOREBAT_API = "https://www.scorebat.com/video-api/v3/"
MAX_MESSAGE_LENGTH = 4000  # Pour Telegram

async def fetch_matches():
    async with aiohttp.ClientSession() as session:
        async with session.get(SCOREBAT_API) as resp:
            data = await resp.json()
            matches = []
            response_list = data.get("response", [])
            
            for i, match in enumerate(response_list):
                # Vérifie le type exact
                if isinstance(match, dict):
                    title = match.get("title", "Match inconnu")
                    comp = match.get("competition", {})
                    competition_name = comp.get("name", "Compétition inconnue") if isinstance(comp, dict) else "Compétition inconnue"
                    date = match.get("date", "Date inconnue")
                    matches.append(f"{title} - {competition_name} ({date})")
                else:
                    # Ignore tout ce qui n'est pas un dict
                    print(f"Ignoré {i}: type={type(match)}, valeur={match}")
            return matches

def split_message(text, max_length=MAX_MESSAGE_LENGTH):
    lines = text.split("\n")
    messages = []
    current_msg = ""
    for line in lines:
        if len(current_msg) + len(line) + 1 > max_length:
            messages.append(current_msg)
            current_msg = line
        else:
            current_msg += "\n" + line if current_msg else line
    if current_msg:
        messages.append(current_msg)
    return messages

async def main():
    bot = Bot(token=BOT_TOKEN)
    matches = await fetch_matches()
    if not matches:
        print("Aucun match trouvé aujourd'hui")
        return

    header = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    full_text = header + "\n".join(matches)
    messages = split_message(full_text)

    for msg in messages:
        await bot.send_message(chat_id=CHANNEL_ID, text=msg)
    print(f"{len(matches)} match(es) posté(s) sur Telegram !")

if __name__ == "__main__":
    asyncio.run(main())
