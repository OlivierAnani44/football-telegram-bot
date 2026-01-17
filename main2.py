import os
import json
import logging
import random
import asyncio
import feedparser
import re
from datetime import datetime, date
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
STATS_FILE = "stats.json"

MAX_POSTED_LINKS = 2500
MAX_POSTS_PER_DAY = 10   # 🔥 LIMITE JOURNALIÈRE
POST_INTERVAL = 300
SCAN_INTERVAL = 300

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("RSS-BOT")

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

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"date": str(date.today()), "count": 0}

def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

posted_links = load_posted()
stats = load_stats()

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
    return (
        f"{random.choice(EMOJI_CATEGORIES[cat])} {random.choice(PHRASES_ACCROCHE[cat])}\n\n"
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
async def publish(message, photo):
    for channel in CHANNELS:
        await bot.send_photo(
            chat_id=channel,
            photo=photo,
            caption=message,
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(3)

# ================= LOOP =================
async def rss_loop():
    global stats

    while True:
        # 🔄 Reset journalier
        if stats["date"] != str(date.today()):
            stats = {"date": str(date.today()), "count": 0}
            save_stats()

        if stats["count"] >= MAX_POSTS_PER_DAY:
            logger.info("⏸ Limite journalière atteinte")
            await asyncio.sleep(SCAN_INTERVAL)
            continue

        try:
            for url in RSS_FEEDS:
                feed = feedparser.parse(url)

                for entry in feed.entries:
                    uid = entry_uid(entry)
                    image = get_image(entry)

                    if uid in posted_links or not image:
                        continue

                    posted_links.add(uid)
                    save_posted()

                    msg = build_message(
                        entry.get("title", ""),
                        entry.get("summary", ""),
                        feed.feed.get("title", "Média")
                    )

                    await publish(msg, image)

                    stats["count"] += 1
                    save_stats()

                    logger.info(f"✅ Publié ({stats['count']}/{MAX_POSTS_PER_DAY})")

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
