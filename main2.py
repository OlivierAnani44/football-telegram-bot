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
    "https://www.allocine.fr/rss/news.xml",
    "https://www.seriesaddict.fr/rss/news.xml"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500
POST_INTERVAL = 300   # 5 minutes
SCAN_INTERVAL = 300   # 5 minutes

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("RSS-BOT")

# ================= BOT =================
bot = Bot(token=BOT_TOKEN)

# ================= UI =================
EMOJI_CATEGORIES = {
    "sortie": ["🎬", "🍿", "🎥"],
    "critique": ["⭐", "📝"],
    "bande_annonce": ["▶️", "🎞️"],
    "casting": ["🎭"],
    "general": ["📰", "🔥"]
}

PHRASES_ACCROCHE = {
    "general": ["📰 INFO : ", "⚡ ACTU : "],
    "sortie": ["🍿 Nouvelle sortie : "],
    "critique": ["⭐ Critique : "],
    "bande_annonce": ["▶️ Bande-annonce : "],
    "casting": ["🎭 Casting : "]
}

HASHTAGS = ["#Film", "#Série", "#Cinéma", "#Actu"]

# ================= STORAGE =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    clean = list(posted_links)[-MAX_POSTED_LINKS:]
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

posted_links = load_posted()

# ================= UTILS =================
def clean_text(text, limit):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")

def entry_uid(entry):
    uid = entry.get("id") or entry.get("guid") or entry.get("link") or entry.get("title")
    return uid.strip().lower()

# ================= ANALYSE =================
def detect_category(title, summary):
    t = f"{title} {summary}".lower()
    if "bande" in t or "trailer" in t:
        return "bande_annonce"
    if "critique" in t:
        return "critique"
    if "casting" in t:
        return "casting"
    if "sortie" in t or "film" in t or "cinéma" in t:
        return "sortie"
    return "general"

def build_message(title, summary, source):
    cat = detect_category(title, summary)
    emoji = random.choice(EMOJI_CATEGORIES[cat])
    accroche = random.choice(PHRASES_ACCROCHE[cat])

    return (
        f"{emoji} {accroche}\n\n"
        f"<b><i>{escape(clean_text(title, 80))}</i></b>\n\n"
        f"<blockquote>{escape(clean_text(summary, 400))}</blockquote>\n\n"
        f"📰 <b>Source :</b> <code>{escape(source)}</code>\n"
        f"🕐 <b>Publié :</b> <code>{datetime.now().strftime('%H:%M')}</code>\n"
        f"📊 <b>Catégorie :</b> {cat.upper()}\n\n"
        f"{' '.join(HASHTAGS)}"
    )

# ================= IMAGE =================
def get_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

# ================= TELEGRAM =================
async def publish(message, photo=None):
    for channel in CHANNELS:
        try:
            if photo:
                await bot.send_photo(channel, photo=photo, caption=message, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(channel, message, parse_mode=ParseMode.HTML)
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Telegram error {channel} : {e}")

# ================= LOOP =================
async def rss_loop():
    while True:
        try:
            for url in RSS_FEEDS:
                feed = feedparser.parse(url)
                entries = sorted(
                    feed.entries,
                    key=lambda e: e.get("published_parsed", datetime.now()),
                    reverse=True
                )

                for entry in entries:
                    uid = entry_uid(entry)

                    if uid in posted_links:
                        continue

                    # 🔒 LOCK AVANT ENVOI
                    posted_links.add(uid)
                    save_posted()

                    msg = build_message(
                        entry.get("title", ""),
                        entry.get("summary", ""),
                        feed.feed.get("title", "Média")
                    )

                    await publish(msg, get_image(entry))
                    logger.info("✅ Article publié")

                    await asyncio.sleep(POST_INTERVAL)
                    raise StopIteration
        except StopIteration:
            pass
        except Exception as e:
            logger.error(f"RSS error : {e}")

        await asyncio.sleep(SCAN_INTERVAL)

# ================= MAIN =================
if __name__ == "__main__":
    asyncio.run(rss_loop())
