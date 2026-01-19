import os
import re
import time
import logging
import asyncio
import feedparser
import requests
from html import escape
from telegram import Bot
from deep_translator import LibreTranslator

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

POSTED_FILE = "posted.txt"
IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

# ================= UTILS =================
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def translate_safe(text: str) -> str:
    text = clean_text(text)

    if not text or len(text) < 3:
        return text

    text = text[:4000]

    try:
        translator = LibreTranslator(
            source="en",
            target="fr",
            base_url="https://libretranslate.de"
        )
        translated = translator.translate(text)
        return translated if translated else text

    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text


def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(f.read().splitlines())


def save_posted(link):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")


def download_image(url, filename):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(filename, "wb") as f:
                f.write(r.content)
            return filename
    except:
        pass
    return None

# ================= MAIN =================
async def run():
    posted = load_posted()

    while True:
        for feed_url in RSS_FEEDS:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:5]:
                link = entry.get("link")
                if not link or link in posted:
                    continue

                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))

                text_en = f"{title}\n\n{summary}"
                text_fr = translate_safe(text_en)

                message = f"<b>{escape(text_fr)}</b>\n\n🔗 {escape(link)}"

                image_path = None
                if "media_content" in entry:
                    img_url = entry.media_content[0].get("url")
                    if img_url:
                        image_path = download_image(
                            img_url,
                            f"{IMAGE_DIR}/{hash(link)}.jpg"
                        )

                for ch in CHANNELS:
                    try:
                        if image_path:
                            with open(image_path, "rb") as img:
                                await bot.send_photo(
                                    chat_id=ch,
                                    photo=img,
                                    caption=message,
                                    parse_mode="HTML"
                                )
                        else:
                            await bot.send_message(
                                chat_id=ch,
                                text=message,
                                parse_mode="HTML"
                            )

                        logger.info(f"✅ Publié sur {ch}")

                    except Exception as e:
                        logger.error(f"❌ Erreur Telegram : {e}")

                posted.add(link)
                save_posted(link)

                await asyncio.sleep(3)

        await asyncio.sleep(60)


# ================= START =================
if __name__ == "__main__":
    logger.info("🤖 Bot Telegram RSS -> Public démarré")
    asyncio.run(run())
