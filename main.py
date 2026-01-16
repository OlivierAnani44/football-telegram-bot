import os
import json
import logging
import asyncio
from pyrogram import Client, filters

# ---------------- CONFIGURATION ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = "@ActuFootZoneFr"
CHANNELS = os.getenv("CHANNELS")  # Liste de canaux séparés par des virgules
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------- POSTÉ ----------------
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                links = set(json.load(f))
                if len(links) > MAX_POSTED_LINKS:
                    links = set(list(links)[-MAX_POSTED_LINKS:])
                logger.info(f"📁 {len(links)} messages chargés")
                return links
    except Exception as e:
        logger.error(f"❌ Erreur chargement: {e}")
    return set()

def save_posted_links():
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_links), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")

posted_links = load_posted_links()

# ---------------- TRANSFERT ----------------
async def forward_message(client, text, photo=None):
    for channel in CHANNELS:
        try:
            if photo:
                await client.send_photo(chat_id=channel, photo=photo, caption=text)
            else:
                await client.send_message(chat_id=channel, text=text)
            logger.info(f"✅ Publié sur {channel}")
        except Exception as e:
            logger.error(f"❌ Erreur publication {channel}: {e}")
        await asyncio.sleep(0.5)  # petite pause pour éviter le flood

# ---------------- CLIENT ----------------
app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Handler pour les nouveaux messages du canal source
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def new_message_handler(client, message):
    msg_id = str(message.message_id)
    if msg_id in posted_links:
        return

    text = message.text or message.caption
    if not text:
        return

    # Filtre les messages contenant des liens ou le code promo ATEN10
    if "http" in text.lower() or "aten10" in text.lower():
        return

    photo = None
    if message.photo:
        photo = message.photo.file_id  # on utilise la photo telle quelle

    await forward_message(client, text, photo)
    posted_links.add(msg_id)
    save_posted_links()

# ---------------- MAIN ----------------
if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS or not API_ID or not API_HASH:
        logger.error("❌ BOT_TOKEN, CHANNELS, API_ID et API_HASH requis")
        exit(1)

    logger.info("🤖 Bot Telegram Football en écoute...")
    app.run()
