import os
import feedparser
import json
import asyncio
import logging
import re
import openai
from telegram import Bot

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

POSTED_FILE = "posted.json"
DEFAULT_IMAGE = "https://i.imgur.com/7vQKX0l.png"  # image par défaut si RSS n'en fournit pas

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
    return DEFAULT_IMAGE

# 🔤 Échappement MarkdownV2
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"""
    return ''.join(['\\' + c if c in escape_chars else c for c in text])

# 🚀 Réécriture de l'article avec IA pour Telegram (français et accrocheur)
async def rewrite_article(text):
    # Supprimer les liens
    text_no_links = re.sub(r'http\S+', '', text)

    # Prompt stable pour éviter les erreurs de f-string
    prompt = f"""Réécris ce texte en français pour Telegram de manière dynamique et accrocheuse.
Utilise des phrases courtes, des emojis football ⚽🔥📰, et rends-le captivant.
Ne mets aucun lien.

{text_no_links}"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        rewritten = response['choices'][0]['message']['content'].strip()
        return rewritten
    except Exception as e:
        logging.error(f"Erreur IA : {e}")
        return text_no_links[:300] + "..."

# 📰 Publication des news immédiatement dès qu'elles sont nouvelles
async def check_and_post_news():
    new_posts = 0
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # prendre quelques derniers articles
            if entry.link in posted_links:
                continue

            # Réécriture de l'article
            summary = await rewrite_article(entry.summary)
            title = escape_markdown(entry.title)
            summary = escape_markdown(summary)

            message = f"""⚽ *ACTUALITÉ FOOTBALL*\n
🔥 *{title}*\n
📰 {summary}"""

            image_url = get_image(entry)

            try:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=message,
                    parse_mode="MarkdownV2"
                )
                posted_links.add(entry.link)
                save_posted_links()
                new_posts += 1
                await asyncio.sleep(5)

            except Exception as e:
                logging.error(f"Erreur lors de l'envoi du post : {e}")

    if new_posts:
        print(f"✅ {new_posts} nouvel(le)(s) article(s) publié(s).")
    else:
        print("⏱ Aucun nouvel article pour l'instant.")

# 🔁 Boucle de vérification en continu (toutes les 1 minute)
async def scheduler():
    while True:
        await check_and_post_news()
        await asyncio.sleep(60)  # vérifie toutes les minutes

# 🏁 Lancement
if __name__ == "__main__":
    print("🤖 Bot football avec IA et publication instantanée lancé...")
    asyncio.run(scheduler())

