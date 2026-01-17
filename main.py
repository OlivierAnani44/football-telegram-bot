import os
import json
import time
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait

# ---------------- CONFIG ----------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")
CHANNELS_RAW = os.getenv("CHANNELS")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
MAX_MESSAGES_PER_CHECK = int(os.getenv("MAX_MESSAGES_PER_CHECK", "20"))
FILTER_KEYWORDS = os.getenv("FILTER_KEYWORDS", "").lower().split(",")

POSTED_FILE = "posted.json"

# ---------------- LOG ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------- CHANNELS ----------------
CHANNELS = []
for c in CHANNELS_RAW.split(","):
    c = c.strip()
    if c.startswith("@"):
        CHANNELS.append(c)
    else:
        CHANNELS.append(int(c))

# ---------------- POSTED ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f).get("posted_ids", []))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump({"posted_ids": list(posted)}, f, indent=2)

posted = load_posted()

# ---------------- UTILS ----------------
def should_filter_message(text):
    if not text:
        return False
    text = text.lower()
    if "http" in text:
        return True
    return any(k for k in FILTER_KEYWORDS if k and k in text)

def extract_text(message):
    return message.text or message.caption or ""

# ---------------- CLIENT ----------------
app = Client(
    "forward_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=50
)

# ---------------- REALTIME ----------------
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def realtime_handler(client, message):
    msg_id = f"{message.chat.id}:{message.id}"
    if msg_id in posted:
        return

    text = extract_text(message)

    if should_filter_message(text):
        posted.add(msg_id)
        save_posted()
        return

    await forward_message(client, message, text)
    posted.add(msg_id)
    save_posted()

# ---------------- FORWARD ----------------
async def forward_message(client, message, text):
    for channel in CHANNELS:
        try:
            await message.copy(chat_id=channel)
            await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.error(f"Erreur {channel}: {e}")

# ---------------- SCANNER ----------------
async def periodic_scanner():
    while True:
        await asyncio.sleep(CHECK_INTERVAL)

        async for message in app.get_chat_history(
            SOURCE_CHANNEL,
            limit=MAX_MESSAGES_PER_CHECK
        ):
            msg_id = f"{message.chat.id}:{message.id}"
            if msg_id in posted:
                continue

            text = extract_text(message)
            if should_filter_message(text):
                posted.add(msg_id)
                continue

            await forward_message(app, message, text)
            posted.add(msg_id)

        save_posted()
        logger.info("📊 Scan terminé")

# ---------------- MAIN ----------------
async def main():
    await app.start()
    logger.info("🤖 Bot démarré")

    asyncio.create_task(periodic_scanner())
    await idle()

    await app.stop()
    save_posted()
    logger.info("🛑 Bot arrêté")

if __name__ == "__main__":
    asyncio.run(main())
