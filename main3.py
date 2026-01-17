import os
import json
import logging
import random
import asyncio
import aiohttp
import feedparser
import re
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from bs4 import BeautifulSoup
from html import escape

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://www.footmercato.net/rss/actus",
    "https://www.foot01.com/rss/actus.xml",
    "https://www.sofoot.com/feed",
    "https://www.goal.com/fr/feeds/news?fmt=rss",
    "https://www.90min.com/feeds/news",
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 3000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# ================= LOGS =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("FootballUltimateBot")

logger.info("⚽ BOT FOOTBALL ULTIME DÉMARRÉ")

# ================= BOT =================
bot = Bot(token=BOT_TOKEN)

# ================= STOCKAGE =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links), f, ensure_ascii=False)

posted_links = load_posted()

# ================= UTILS =================
def clean_text(text, limit=400):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + "..." if len(text) > limit else text

def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

# ================= ANALYSE =================
def detect_category(title):
    t = title.lower()
    if any(w in t for w in ["transfert", "mercato", "signature"]):
        return "🔄 TRANSFERT"
    if any(w in t for w in ["victoire", "défaite", "score", "but"]):
        return "📊 RÉSULTAT"
    if any(w in t for w in ["match", "face à", "contre"]):
        return "⚽ MATCH"
    return "📰 ACTU FOOT"

def build_message(entry, source):
    title = clean_text(entry.get("title", ""), 90)
    summary = clean_text(entry.get("summary", ""), 420)
    category = detect_category(title)

    return (
        f"{category}\n\n"
        f"<b>{escape(title)}</b>\n\n"
        f"<blockquote>{escape(summary)}</blockquote>\n\n"
        f"📰 <b>Source :</b> {escape(source)}\n"
        f"🕒 <b>Heure :</b> {datetime.now().strftime('%H:%M')}\n\n"
        "#Football #Foot #ActuFoot"
    )

# ================= POST =================
async def post(message, photo=None):
    for ch in CHANNELS:
        try:
            if photo:
                await bot.send_photo(ch, photo=photo, caption=message, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(ch, message, parse_mode=ParseMode.HTML)
            logger.info(f"✅ Publié sur {ch}")
        except Exception as e:
            logger.error(f"❌ Telegram erreur {ch}: {e}")
        await asyncio.sleep(4)

# ================= FETCH RSS =================
async def fetch_feed(session, url):
    async with session.get(url, headers=HEADERS, timeout=20) as r:
        text = await r.text()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: feedparser.parse(text))

# ================= MAIN LOOP =================
async def rss_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            for url in RSS_FEEDS:
                try:
                    feed = await fetch_feed(session, url)
                    logger.info(f"📡 {url} → {len(feed.entries)} articles")

                    for entry in feed.entries[:5]:  # limite anti-spam
                        link = entry.get("link")
                        if not link or link in posted_links:
                            continue

                        msg = build_message(entry, feed.feed.get("title", "Football"))
                        img = extract_image(entry)

                        await post(msg, img)
                        posted_links.add(link)
                        save_posted()
                        await asyncio.sleep(6)

                except Exception as e:
                    logger.error(f"❌ RSS erreur {url}: {e}")

            logger.info("⏳ Pause 10 minutes")
            await asyncio.sleep(600)

# ================= START =================
if __name__ == "__main__":
    asyncio.run(rss_loop())
