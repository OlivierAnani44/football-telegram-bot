import os
import json
import logging
import asyncio
from pyrogram import Client, filters

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS").split(",")]

POSTED_FILE = "posted.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chargement des messages déjà transférés
def load_posted_links():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted_links(links):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(links), f, ensure_ascii=False, indent=2)

posted_links = load_posted_links()

# Transfert des messages vers les canaux
async def forward_message(client, text, photo=None):
    for channel in CHANNELS:
        try:
            if photo:
                await client.send_photo(chat_id=channel, photo=photo, caption=text)
            else:
                await client.send_message(chat_id=channel, text=text)
            logger.info(f"✅ Message transféré sur {channel}")
        except Exception as e:
            logger.error(f"❌ Erreur publication {channel}: {e}")
        await asyncio.sleep(0.5)

# Client utilisateur
app = Client("user_session", api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.chat(SOURCE_CHANNEL))
async def new_message_handler(client, message):
    msg_id = str(message.message_id)
    if msg_id in posted_links:
        return

    text = message.text or message.caption
    if not text:
        return

    if "http" in text.lower() or "aten10" in text.lower():
        return

    photo = message.photo.file_id if message.photo else None

    await forward_message(client, text, photo)
    posted_links.add(msg_id)
    save_posted_links(posted_links)

if __name__ == "__main__":
    logger.info("🤖 Bot Telegram en écoute...")
    app.run()
