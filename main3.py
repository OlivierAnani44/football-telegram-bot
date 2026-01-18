import os
import asyncio
import feedparser
from datetime import datetime, timezone
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")        # Ton token Telegram
CHANNEL_ID = os.getenv("CHANNEL_ID")      # Ton canal Telegram, ex: @ton_canal
RSS_URL = "https://www.livescore.com/rss/football"  # Flux RSS matchs du jour
CHECK_INTERVAL = 3600                     # Vérifie toutes les heures
MAX_MESSAGE_LENGTH = 4000                 # Limite Telegram
POSTED_FILE = "posted_matches.txt"        # Pour éviter doublons

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

async def fetch_matches():
    feed = feedparser.parse(RSS_URL)
    today = datetime.now(timezone.utc).date()
    matches = []

    for entry in feed.entries:
        title = entry.title
        # Essayer de parser la date du flux RSS
        if hasattr(entry, "published_parsed"):
            match_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).date()
        else:
            continue

        if match_date == today:
            matches.append(f"{title} ({entry.published})")
    return matches

async def post_matches(bot):
    posted = load_posted()
    matches = await fetch_matches()
    new_matches = [m for m in matches if m not in posted]

    if not new_matches:
        print("Aucun nouveau match à poster pour aujourd'hui")
        return

    header = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    full_text = header + "\n".join(new_matches)
    messages = split_message(full_text)

    for msg in messages:
        await bot.send_message(chat_id=CHANNEL_ID, text=msg)

    print(f"{len(new_matches)} match(es) posté(s) sur Telegram !")
    posted.update(new_matches)
    save_posted(posted)

async def main():
    bot = Bot(token=BOT_TOKEN)
    while True:
        await post_matches(bot)
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
