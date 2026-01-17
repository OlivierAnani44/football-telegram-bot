import os
import json
import logging
import asyncio
from pyrogram import Client, filters

# ---------------- CONFIG ----------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")
CHANNELS = os.getenv("CHANNELS", "")

if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, CHANNELS]):
    raise RuntimeError("❌ Variables d'environnement manquantes")

API_ID = int(API_ID)
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

POSTED_FILE = "posted.json"
MAX_POSTED = 3000

# ---------------- LOG ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------- POSTED ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f)

posted = load_posted()

# ---------------- BOT ----------------
app = Client(
    name="football_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True   # 🔥 IMPORTANT
)

# ---------------- HANDLER ----------------
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def handler(client, message):
    msg_id = str(message.id)
    if msg_id in posted:
        return

    text = message.text or message.caption
    if not text:
        return

    text_low = text.lower()
    if "http" in text_low or "aten10" in text_low:
        return

    for ch in CHANNELS:
        try:
            if message.photo:
                await client.send_photo(
                    chat_id=ch,
                    photo=message.photo.file_id,
                    caption=text
                )
            else:
                await client.send_message(ch, text)
            logger.info(f"✅ Envoyé vers {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur {ch}: {e}")
        await asyncio.sleep(0.6)

    posted.add(msg_id)
    save_posted()

# ---------------- STA
