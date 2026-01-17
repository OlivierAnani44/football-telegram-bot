import os
import json
import logging
import random
import asyncio
import aiohttp
import feedparser
import re
import hashlib
import time
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from bs4 import BeautifulSoup
from html import escape

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
MAX_POSTS_PER_HOUR = int(os.getenv("MAX_POSTS_PER_HOUR", "6"))
FILTER_KEYWORDS = [k.strip().lower() for k in os.getenv("FILTER_KEYWORDS", "").split(",") if k]

RSS_FEEDS = [
    "https://www.allocine.fr/rss/news.xml",
    "https://www.seriesaddict.fr/rss/news.xml"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RSS-BOT")

bot = Bot(token=BOT_TOKEN)

# ---------------- EMOJIS ----------------
EMOJI = ["📰", "🔥", "🎬", "🍿", "⭐", "🎞️", "🚀"]

HASHTAGS = ["#Film", "#Serie", "#Cinema", "#Actu"]

# ---------------- POSTED ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links)[-MAX_POSTED_LINKS:], f, ensure_ascii=False)

posted_links = load_posted()
POST_TIMESTAMPS = []

# ---------------- UTILS ----------------
def clean_text(text, max_len=400):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")

def make_uid(entry, feed_url):
    base = (
        entry.get("title", "") +
        entry.get("summary", "") +
        entry.get("published", "") +
        feed_url
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def can_post():
    now = time.time()
    POST_TIMESTAMPS[:] = [t for t in POST_TIMESTAMPS if now - t < 3600]
    return len(POST_TIMESTAMPS) < MAX_POSTS_PER_HOUR

def keyword_allowed(title, summary):
    if not FILTER_KEYWORDS:
        return True
    text = f"{title} {summary}".lower()
    return any(k in text for k in FILTER_KEYWORDS)

# ---------------- IMAGE ----------------
def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    summary = entry.get("summary", "")
    soup = BeautifulSoup(summary, "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

# ---------------- MESSAGE ----------------
def build_message(title, summary, source):
    title = escape(clean_text(title, 80))
    summary = escape(clean_text(summary, 350))
    emoji = random.choice(EMOJI)
    hashtags = " ".join(random.sample(HASHTAGS, min(len(HASHTAGS), 4)))

    return (
        f"{emoji} <b>ACTU</b>\n\n"
        f"<b><i>{title}</i></b>\n\n"
        f"<blockquote>{summary}</blockquote>\n\n"
        f"📰 <b>Source :</b> <code>{escape(source)}</code>\n"
        f"🕒 <b>{datetime.now().strftime('%H:%M')}</b>\n\n"
        f"{hashtags}"
    )

# ---------------- TELEGRAM ----------------
async def post(message, image=None):
    for channel in CHANNELS:
        try:
            if image:
                await bot.send_photo(channel, image, caption=message, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(channel, message, parse_mode=ParseMode.HTML)
            logger.info(f"✅ Posté sur {channel}")
        except Exception as e:
            logger.error(f"❌ Telegram {channel} : {e}")
        await asyncio.sleep(random.randint(3, 6))

# ---------------- RSS ----------------
async def fetch_feed(session, url):
    async with session.get(url, timeout=20) as r:
        data = await r.text()
        return feedparser.parse(data)

async def rss_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                for feed_url in RSS_FEEDS:
                    feed = await fetch_feed(session, feed_url)

                    for entry in feed.entries:
                        uid = make_uid(entry, feed_url)

                        if uid in posted_links:
                            continue

                        title = entry.get("title", "")
                        summary = entry.get("summary", "")

                        if not keyword_allowed(title, summary):
                            continue

                        if not can_post():
                            logger.warning("⏳ Limite horaire atteinte")
                            break

                        img = extract_image(entry)
                        msg = build_message(title, summary, feed.feed.get("title", "Média"))

                        await post(msg, img)

                        posted_links.add(uid)
                        POST_TIMESTAMPS.append(time.time())
                        save_posted()

                        # ✅ 1 POST PAR CYCLE
                        await asyncio.sleep(300)
                        break

                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"🔥 Crash évité : {e}")
                await asyncio.sleep(60)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    logger.info("🤖 Bot RSS démarré")
    asyncio.run(rss_loop())
