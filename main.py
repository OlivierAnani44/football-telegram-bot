import os
import feedparser
import logging
from html import unescape
from deep_translator import GoogleTranslator
import requests
from telegram import Bot
import asyncio
import json

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Telegram bot token
CHANNELS = os.getenv("CHANNELS", "").split(",")  # Canaux séparés par des virgules
RSS_FEED = "https://feeds.bbci.co.uk/sport/football/rss.xml"  # Exemple RSS
CHECK_INTERVAL = 300  # Vérifier toutes les 5 minutes

POSTED_FILE = "posted.json"  # Pour garder la trace des articles déjà postés
TEMP_IMAGE_FILE = "image.jpg"

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

# ---------------- UTILITAIRES ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted_set):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_set), f)

def get_latest_rss_item(rss_url):
    feed = feedparser.parse(rss_url)
    if feed.entries:
        entry = feed.entries[0]
        title = unescape(entry.get('title', ''))
        summary = unescape(entry.get('summary', ''))
        link = entry.get('link', '')
        media = entry.get('media_content', [])
        image_url = media[0]['url'] if media else None
        return title, summary, link, image_url
    return None, None, None, None

def translate_text(text):
    try:
        return GoogleTranslator(source='en', target='fr').translate(text)
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text

def download_image(url, filename):
    if not url:
        return False
    try:
        r = requests.get(url)
        if r.status_code == 200:
            with open(filename, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        logger.error(f"❌ Erreur téléchargement image : {e}")
    return False

def publish_telegram(text, image_path=None):
    for ch in CHANNELS:
        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as img:
                    bot.send_photo(chat_id=ch, photo=img, caption=text)
            else:
                bot.send_message(chat_id=ch, text=text, parse_mode="HTML")
            logger.info(f"✅ Publié sur {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur publication sur {ch} : {e}")

# ---------------- MAIN LOOP ----------------
async def main():
    posted_articles = load_posted()
    while True:
        title, summary, link, image_url = get_latest_rss_item(RSS_FEED)
        if title and link not in posted_articles:
            full_text = f"{title}\n\n{summary}\n\n{link}"
            logger.info(f"Texte original : {full_text}")

            translated_text = translate_text(full_text)
            logger.info(f"Texte traduit : {translated_text}")

            # Télécharger image si disponible
            image_exists = download_image(image_url, TEMP_IMAGE_FILE)

            # Publier sur Telegram
            publish_telegram(translated_text, TEMP_IMAGE_FILE if image_exists else None)

            # Marquer comme posté
            posted_articles.add(link)
            save_posted(posted_articles)
        else:
            logger.info("✅ Aucun nouvel article à poster")

        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
