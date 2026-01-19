import os
import feedparser
import asyncio
import logging
import aiohttp
import random
from datetime import datetime
from html import escape as html_escape
from bs4 import BeautifulSoup
from googletrans import Translator
from telegram import Bot
from telegram.constants import ParseMode

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("PUBLIC_CHANNELS", "")
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

RSS_FEEDS = ["https://feeds.bbci.co.uk/sport/football/rss.xml"]

POSTED_FILE = "posted.txt"
IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# ================= LOG =================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ================= TELEGRAM =================
bot = Bot(token=BOT_TOKEN)
translator = Translator()

# ================= STYLE =================
EMOJIS = ["⚽", "🔥", "🏆", "📰"]
ACCROCHES = ["INFO FOOT :", "ACTU FOOT :", "BREAKING FOOT :"]
HASHTAGS = "#Football #Foot #BBCSport"

# ================= UTILS =================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_posted(link):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def clean_text(text, max_len=700):
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text

def translate_safe(text):
    try:
        result = translator.translate(text, src="en", dest="fr")
        return result.text if result else text
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text

def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    if "media_thumbnail" in entry:
        return entry.media_thumbnail[0].get("url")

    soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

async def download_image(url, filename):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status == 200:
                    path = os.path.join(IMAGE_DIR, filename)
                    with open(path, "wb") as f:
                        f.write(await r.read())
                    return path
    except Exception as e:
        logger.error(f"❌ Erreur téléchargement image : {e}")
    return None

def build_message(text_fr):
    emoji = random.choice(EMOJIS)
    accroche = random.choice(ACCROCHES)
    heure = datetime.now().strftime("%H:%M")

    return f"""{emoji} <b>{accroche}</b>

{html_escape(text_fr)}

🕐 <code>{heure}</code>
{HASHTAGS}
"""

# ================= MAIN LOGIC =================
async def process_rss():
    posted = load_posted()

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            link = entry.get("link")
            if not link or link in posted:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")
            image_url = extract_image(entry)

            text_en = clean_text(f"{title}\n\n{summary}")
            text_fr = translate_safe(text_en)
            message = build_message(text_fr)

            image_path = None
            if image_url:
                image_name = link.split("/")[-1].replace("?", "") + ".jpg"
                image_path = await download_image(image_url, image_name)

            for ch in CHANNELS:
                try:
                    if image_path:
                        with open(image_path, "rb") as img:
                            await bot.send_photo(
                                chat_id=ch,
                                photo=img,
                                caption=message,
                                parse_mode=ParseMode.HTML
                            )
                    else:
                        await bot.send_message(
                            chat_id=ch,
                            text=message,
                            parse_mode=ParseMode.HTML
                        )
                    logger.info(f"✅ Publié sur {ch}")
                except Exception as e:
                    logger.error(f"❌ Telegram erreur {ch} : {e}")

            save_posted(link)
            await asyncio.sleep(5)

# ================= LOOP =================
async def main():
    logger.info("🤖 Bot RSS → Texte → Traduction → Image → Telegram démarré")
    while True:
        await process_rss()
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
