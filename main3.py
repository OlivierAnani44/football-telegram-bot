import os
import asyncio
import feedparser
from datetime import datetime
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # @ton_canal
RSS_URL = "https://feeds.bbci.co.uk/sport/football/rss.xml"
CHECK_INTERVAL = 3600  # 1 heure
POSTED_FILE = "posted_matches.txt"
MAX_MESSAGE_LENGTH = 3500  # Telegram max 4096, on laisse une marge

# ================= FONCTIONS =================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        for match in posted:
            f.write(match + "\n")

async def fetch_matches():
    feed = feedparser.parse(RSS_URL)
    matches = []
    for entry in feed.entries:
        # On garde juste le titre pour réduire la taille
        matches.append(entry.title.strip())
    return matches

def split_messages(text, max_length):
    """Découpe le texte en plusieurs messages si nécessaire"""
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

async def post_matches(bot):
    posted = load_posted()
    matches = await fetch_matches()
    new_matches = [m for m in matches if m not in posted]
    
    if not new_matches:
        print("Aucun nouveau match à poster")
        return
    
    header = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    message_text = header + "\n".join(new_matches)
    
    messages = split_messages(message_text, MAX_MESSAGE_LENGTH)
    
    try:
        for msg in messages:
            await bot.send_message(chat_id=CHANNEL_ID, text=msg)
        print(f"{len(new_matches)} match(es) posté(s) sur Telegram !")
        posted.update(new_matches)
        save_posted(posted)
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
