import os
import re
import feedparser
import logging
import aiohttp
import asyncio
from telegram import Bot
from deep_translator import GoogleTranslator

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [ch.strip() for ch in os.getenv("CHANNELS", "").split(",") if ch.strip()]
RSS_FEED = "https://feeds.bbci.co.uk/sport/football/rss.xml"
TEMP_IMAGE_FILE = "/tmp/image.jpg"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

# ---------------- IMAGE EXTRACTION ----------------
def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")

    if "media_thumbnail" in entry:
        return entry.media_thumbnail[0].get("url")

    html = entry.get("summary", "")
    match = re.search(r'<img[^>]+src="([^">]+)"', html)
    return match.group(1) if match else None

async def download_image(url):
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(TEMP_IMAGE_FILE, "wb") as f:
                        f.write(await resp.read())
                    return TEMP_IMAGE_FILE
    except Exception as e:
        logger.error(f"❌ Image error : {e}")
    return None

# ---------------- TRANSLATION ----------------
async def translate(text):
    try:
        return GoogleTranslator(source="auto", target="fr").translate(text)
    except Exception:
        return text

# ---------------- FORMAT ----------------
def format_message(title, summary, published):
    return f"""
🔥🔥 <b>NOUVELLE FOOT :</b> <i>{title}</i>

<blockquote>{summary}</blockquote>

📌 <b>Source :</b> BBC Sport
⏰ <b>Publié :</b> {published}
🏷️ <b>Catégorie :</b> MATCH

#Football #Foot #Afcon #BBCSport
""".strip()

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot lancé")

    feed = feedparser.parse(RSS_FEED)
    if not feed.entries:
        return

    for entry in feed.entries[:5]:
        title = await translate(entry.get("title", ""))
        summary = await translate(
            re.sub("<.*?>", "", entry.get("summary", ""))
        )
        published = entry.get("published", "—")

        image_url = extract_image(entry)
        image_path = await download_image(image_url)

        message = format_message(title, summary, published)

        for ch in CHANNELS:
            try:
                if image_path:
                    with open(image_path, "rb") as img:
                        await bot.send_photo(
                            chat_id=ch,
                            photo=img,
                            caption=message[:1024],
                            parse_mode="HTML"
                        )
                else:
                    await bot.send_message(
                        chat_id=ch,
                        text=message,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )

                logger.info(f"✅ Publié sur {ch}")
            except Exception as e:
                logger.error(f"❌ Telegram error : {e}")

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
