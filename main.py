import os
import feedparser
import logging
import aiohttp
import asyncio
from telegram import Bot
from deep_translator import GoogleTranslator, LibreTranslator, DeeplTranslator

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [ch.strip() for ch in os.getenv("CHANNELS", "").split(",") if ch.strip()]

RSS_FEED = "https://feeds.bbci.co.uk/sport/football/rss.xml"
TEMP_TEXT_FILE = "/tmp/message.txt"
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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(TEMP_IMAGE_FILE, "wb") as f:
                        f.write(await resp.read())
                    return TEMP_IMAGE_FILE
    except Exception as e:
        logger.error(f"❌ Erreur téléchargement image : {e}")
    return None

async def translate_text(text):
    translators = [
        ("Google", GoogleTranslator(source='auto', target='fr')),
        ("Libre", LibreTranslator(source='auto', target='fr')),
        # ("DeepL", DeeplTranslator(source='auto', target='fr')), # Décommenter si clé DeepL
    ]
    for name, translator in translators:
        try:
            translated = translator.translate(text)
            logger.info(f"✅ {name} Translator réussi")
            return translated
        except Exception as e:
            logger.error(f"❌ {name} Translator erreur : {e}")
    # fallback : texte original
    return text

async def publish_telegram(text, image_path=None):
    for ch in CHANNELS:
        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as img:
                    await bot.send_photo(chat_id=ch, photo=img, caption=text)
            else:
                await bot.send_message(chat_id=ch, text=text, parse_mode="HTML")
            logger.info(f"✅ Publié sur {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur publication sur {ch} : {e}")

# ---------------- MAIN LOOP ----------------
async def main():
    logger.info("🤖 Bot Telegram RSS -> Public démarré")
    
    feed = await fetch_rss()
    if not feed.entries:
        logger.warning("❌ Aucun article trouvé")
        return
    
    for entry in feed.entries[:5]:  # prend les 5 derniers
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        link = entry.get("link", "")
        text = f"{title}\n{summary}\n{link}"
        
        # Enregistre temporairement
        with open(TEMP_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(text)
        
        # Télécharge l'image si présente
        image_url = entry.get("media_content", [{}])[0].get("url")
        image_path = await download_image(image_url) if image_url else None
        
        # Traduction
        translated_text = await translate_text(text)
        logger.info(f"Texte traduit : {translated_text}")
        
        # Publication
        await publish_telegram(translated_text, image_path)
        await asyncio.sleep(5)  # petit délai pour éviter le spam

if __name__ == "__main__":
    asyncio.run(main())
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
        GoogleTranslator(source='auto', target='fr'),
        LibreTranslator(source='auto', target='fr')
    ]
    for translator in translators:
        try:
            return translator.translate(text)
        except:
            pass
    return text

def format_message(title, summary):
    return f"""
🔥🔥 <b>NOUVELLE FOOT :</b> <i>{title}</i>

<blockquote>{summary}</blockquote>

📰 <b>Source :</b> BBC Sport  
⏰ <b>Publié :</b> aujourd’hui  
🏟 <b>Catégorie :</b> MATCH

#Football #Foot #PremierLeague #Ligue1 #SerieA
""".strip()

async def publish_telegram(text, image_path=None):
    for ch in CHANNELS:
        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as img:
                    await bot.send_photo(
                        chat_id=ch,
                        photo=img,
                        caption=text,
                        parse_mode="HTML"
                    )
            else:
                await bot.send_message(
                    chat_id=ch,
                    text=text,
                    parse_mode="HTML"
                )
            logger.info(f"✅ Publié sur {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur publication : {e}")

# ---------------- MAIN LOOP ----------------
async def main():
    logger.info("🤖 Bot RSS Telegram démarré")

    feed = await fetch_rss()
    if not feed.entries:
        logger.warning("❌ Aucun article")
        return

    for entry in feed.entries[:5]:
        title_en = entry.get("title", "")
        summary_en = entry.get("summary", "")

        # Traduction
        title_fr = await translate_text(title_en)
        summary_fr = await translate_text(summary_en)

        # Image
        image_url = entry.get("media_content", [{}])[0].get("url")
        image_path = await download_image(image_url) if image_url else None

        # Format final (SANS LIEN)
        message = format_message(title_fr, summary_fr)

        # Publication
        await publish_telegram(message, image_path)
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
