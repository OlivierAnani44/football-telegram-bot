import os
import feedparser
import logging
import aiohttp
import asyncio
from telegram import Bot
from deep_translator import GoogleTranslator, LibreTranslator

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

# ---------------- UTILITIES ----------------
async def fetch_rss():
    return feedparser.parse(RSS_FEED)

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
        logger.error(f"❌ Erreur image : {e}")
    return None

async def translate_text(text):
    translators = [
        GoogleTranslator(source="auto", target="fr"),
        LibreTranslator(source="auto", target="fr")
    ]
    for tr in translators:
        try:
            return tr.translate(text)
        except Exception:
            continue
    return text

def format_message(title, summary, published):
    return f"""🔥🔥 <b>NOUVELLE FOOT</b>

<b>{title}</b>

📰 {summary}

📌 <b>Source :</b> BBC Sport
⏰ <b>Publié :</b> {published}
🏷️ <b>Catégorie :</b> MATCH

#Football #Foot #Afcon #BBCSport
""".strip()

async def publish():
    logger.info("🤖 Bot démarré")

    feed = await fetch_rss()
    if not feed.entries:
        logger.warning("❌ Aucun article trouvé")
        return

    for entry in feed.entries[:5]:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        published = entry.get("published", "—")

        image_url = entry.get("media_content", [{}])[0].get("url")
        image_path = await download_image(image_url)

        title_fr = await translate_text(title)
        summary_fr = await translate_text(summary)

        message = format_message(title_fr, summary_fr, published)

        for ch in CHANNELS:
            try:
                if image_path and os.path.exists(image_path):
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
                logger.error(f"❌ Erreur {ch} : {e}")

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(publish())
