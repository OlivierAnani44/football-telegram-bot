import os
import feedparser
import json
import asyncio
import logging
import re
import random
import uuid
from datetime import datetime

import aiohttp
from telegram import Bot
from bs4 import BeautifulSoup

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS", "")
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

RSS_FEED = "https://fr.cointelegraph.com/rss"
POSTED_FILE = "posted.json"
IMAGE_DIR = "images"

MIN_DELAY = 300  # 5 minutes
MAX_POSTED = 3000

os.makedirs(IMAGE_DIR, exist_ok=True)

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("CT_BOT")

bot = Bot(token=BOT_TOKEN)

# ================= STYLE =================
ACCROCHES = [
    "🚀 <b>BREAKING CRYPTO</b>",
    "📊 <b>MARCHÉ CRYPTO</b>",
    "🔥 <b>ACTU BLOCKCHAIN</b>"
]

HASHTAGS = ["#Crypto", "#Bitcoin", "#Ethereum", "#Blockchain", "#Web3"]

COMMENTS = [
    "💬 <i>Ton avis ?</i>",
    "📊 <i>Bullish ou bearish ?</i>",
    "🔥 <i>Impact réel selon toi ?</i>",
]

POPULAR_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth",
    "etf", "sec", "regulation", "adoption",
    "crash", "hack", "institutional"
]

# ================= STORAGE =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # format: {"channel_id": ["link1", "link2", ...], ...}
                return {ch: set(lst) for ch, lst in data.items()}
        except:
            pass
    return {ch: set() for ch in CHANNELS}

def save_posted():
    data = {ch: list(posted_links[ch])[-MAX_POSTED:] for ch in posted_links}
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

posted_links = load_posted()

# ================= TEXT =================
def clean_text(text, max_len=600):
    text = BeautifulSoup(text or "", "html.parser").get_text()
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text

def highlight_keywords(text):
    for kw in POPULAR_KEYWORDS:
        text = re.sub(
            rf"\b({kw})\b",
            r"<b>\1</b>",
            text,
            flags=re.IGNORECASE
        )
    return text

# ================= IMAGE =================
def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    if "media_thumbnail" in entry:
        return entry.media_thumbnail[0].get("url")
    return None

async def download_crypto_image():
    url = "https://source.unsplash.com/1200x675/?crypto,bitcoin"
    filename = f"{IMAGE_DIR}/{uuid.uuid4().hex}.jpg"

    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            if r.status == 200:
                with open(filename, "wb") as f:
                    f.write(await r.read())
                return filename
    return None

# ================= MESSAGE =================
def build_message(title, summary):
    accroche = random.choice(ACCROCHES)
    hashtags = " ".join(random.sample(HASHTAGS, 3))

    title = highlight_keywords(clean_text(title, 100))
    summary = highlight_keywords(clean_text(summary))

    return f"""
{accroche}

<b>{title}</b>

<blockquote>
<i>{summary}</i>
</blockquote>

📌 <b>Détails techniques</b> :
<code>source=Cointelegraph | type=crypto_news</code>

⏰ <i>{datetime.now().strftime('%H:%M')}</i>

{hashtags}
"""

# ================= TELEGRAM =================
async def post(channel, photo, message):
    try:
        if photo and photo.startswith("http"):
            sent = await bot.send_photo(channel, photo, caption=message, parse_mode="HTML")
        elif photo:
            with open(photo, "rb") as f:
                sent = await bot.send_photo(channel, f, caption=message, parse_mode="HTML")
        else:
            sent = await bot.send_message(channel, message, parse_mode="HTML")

        await bot.send_message(
            channel,
            random.choice(COMMENTS),
            reply_to_message_id=sent.message_id,
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logger.error(f"❌ Erreur en postant sur {channel} : {e}")
        return False

# ================= LOOP =================
async def rss_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(RSS_FEED, timeout=20) as r:
                    feed = feedparser.parse(await r.text())

                    for entry in feed.entries:
                        uid = entry.get("id") or entry.get("link")
                        if not uid:
                            continue

                        title = entry.get("title", "")
                        summary = entry.get("summary", "")
                        img = extract_image(entry)
                        temp = None
                        if not img:
                            temp = await download_crypto_image()

                        msg = build_message(title, summary)

                        posted_somewhere = False
                        for ch in CHANNELS:
                            if uid in posted_links.get(ch, set()):
                                logger.info(f"⏭ Article déjà posté sur {ch}, passage au suivant")
                                continue

                            success = await post(ch, img or temp, msg)
                            if success:
                                posted_links[ch].add(uid)
                                posted_somewhere = True
                                await asyncio.sleep(2)

                        if posted_somewhere:
                            save_posted()
                            if temp and os.path.exists(temp):
                                os.remove(temp)
                            logger.info("✅ Article publié sur au moins un canal")

                        await asyncio.sleep(MIN_DELAY)

            except Exception as e:
                logger.error(f"❌ Erreur RSS : {e}")

            await asyncio.sleep(60)

# ================= MAIN =================
async def main():
    logger.info("🤖 Bot Cointelegraph lancé")
    await rss_loop()

if __name__ == "__main__":
    asyncio.run(main())
