import os
import asyncio
import feedparser
from datetime import datetime
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Exemple : @ton_canal
RSS_URL = "https://feeds.bbci.co.uk/sport/football/rss.xml"  # RSS football BBC FR
CHECK_INTERVAL = 3600  # 1 heure
POSTED_FILE = "posted_matches.txt"  # Pour ne pas reposter le même match

# ================= FONCTIONS =================
def load_posted():
    """Charge les matchs déjà postés"""
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted(posted):
    """Sauvegarde les matchs postés"""
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        for match in posted:
            f.write(match + "\n")

async def fetch_matches():
    """Récupère les matchs depuis le RSS"""
    feed = feedparser.parse(RSS_URL)
    matches = []
    for entry in feed.entries:
        title = entry.title.strip()
        published = entry.published if "published" in entry else ""
        matches.append(f"{title} ({published})")
    return matches

async def post_matches(bot):
    posted = load_posted()
    matches = await fetch_matches()
    new_matches = [m for m in matches if m not in posted]
    
    if not new_matches:
        print("Aucun nouveau match à poster")
        return
    
    message = f"⚽ Matchs du jour ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    message += "\n".join(new_matches)
    
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=message)
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
