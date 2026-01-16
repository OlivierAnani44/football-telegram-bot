import os
import feedparser
import json
import asyncio
import logging
from telegram import Bot

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

POSTED_FILE = "posted.json"

# ⚙️ Initialisation bot et logging
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(filename="bot.log", level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 🔄 Chargement des liens déjà postés
def load_posted_links():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted_links():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links), f, ensure_ascii=False, indent=2)

posted_links = load_posted_links()

# 🖼️ Récupération de l'image depuis le flux RSS
def get_image(entry):
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get('url')
    if "links" in entry:
        for link in entry.links:
            if "image" in link.type:
                return link.href
    return None

# 🔤 Échappement des caractères spéciaux pour MarkdownV2
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"""
    return ''.join(['\\' + c if c in escape_chars else c for c in text])

# 📰 Publication des news (version asynchrone)
async def post_news():
    print("📡 Récupération des flux RSS...")
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        print(f"Flux chargé : {feed_url} ({len(feed.entries)} entrées)")

        for entry in feed.entries[:3]:
            if entry.link in posted_links:
                continue

            title = escape_markdown(entry.title)
            link = entry.link
            summary = escape_markdown(entry.summary[:300] + "...")

            message = f"""⚽ *ACTUALITÉ FOOTBALL*\n
🔥 {title}\n
📰 {summary}\n
🔗 [Lire l'article]({link})"""

            image_url = get_image(entry)

            try:
                if image_url:
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=image_url,
                        caption=message,
                        parse_mode="MarkdownV2"
                    )
                else:
                    await bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message,
                        parse_mode="MarkdownV2"
                    )

                posted_links.add(link)
                save_posted_links()
                await asyncio.sleep(5)  # Petite pause pour éviter le spam

            except Exception as e:
                logging.error(f"Erreur lors de l'envoi du post : {e}")

# 🔁 Boucle de planification toutes les 30 minutes
async def scheduler():
    while True:
        await post_news()
        print("⏱ En attente de la prochaine tâche...")
        await asyncio.sleep(30 * 60)  # 30 minutes

# 🏁 Lancement du bot
if __name__ == "__main__":
    print("🤖 Bot football lancé...")
    asyncio.run(scheduler())
