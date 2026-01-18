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
TELEGRAM_CHECK_LIMIT = 50  # messages à scanner par canal

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
                return {ch: set(v) for ch, v in data.items()}
        except:
            pass
    return {ch: set() for ch in CHANNELS}

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {ch: list(v)[-MAX_POSTED:] for ch, v in posted_links.items()},
            f,
            indent=2
        )

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

# ================= TELEGRAM CHECK =================
async def already_posted_on_channel(channel, title, link):
    try:
        updates = await bot.get_chat_history(
            chat_id=channel,
            limit=TELEGRAM_CHECK_LIMIT
        )
        title = title.lower()
        for msg in updates:
            text = (msg.text or msg.caption or "").lower()
            if link and link in text:
                return True
            if title and title[:40] in text:
