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

# Multi-sources RSS football FR
RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://rmcsport.bfmtv.com/rss/football.xml",
    "https://www.goal.com/fr/feeds/news_10.rss"
]
SOURCE_NAMES = {
    "lequipe": "L'Équipe - Football",
    "rmcsport": "RMC Sport - Football",
    "goal": "Goal FR"
}

POSTED_FILE = "posted.json"
IMAGE_DIR = "images"
MAX_POSTED = 3000

os.makedirs(IMAGE_DIR, exist_ok=True)

# ================= LOG =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("FOOTBOT_FR_MULTI")

bot = Bot(token=BOT_TOKEN)

# ================= STYLE =================
ACCROCHES = [
    "⚽ ACTU FOOT : ",
    "🔥 BREAKING FOOT : ",
    "🏆 MARCHÉ DU FOOT : "
]

HASHTAGS = [
    "#Football", "#Ligue1", "#LigueDesChampions",
    "#Soccer", "#Foot", "#Mercato"
]

COMMENTS = [
    "💬 Votre avis sur ce match ?",
    "⚡ Qu’en pensez-vous ?",
    "🔥 Joueurs clés à suivre ?",
    "🤔 Bonne ou mauvaise nouvelle pour votre club ?",
    "📝 On en discute 👇"
]

POPULAR_KEYWORDS = [
    "ligue", "champions", "match", "but", "score",
    "transfert", "mercato", "joueur", "entraîneur",
    "carton", "blessure", "suspension", "club",
    "france", "europe", "finale", "coupe", "équipe"
]

MIN_TEXT_LENGTH = 150

# ================= STORAGE =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links)[-MAX_POSTED:], f, indent=2, ensure_ascii=False)

posted_links = load_posted()

# ================= TEXT =================
def clean_text(text, max_len=600):
    text = BeautifulSoup(text or "", "html.parser").get_text()
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text

def escape_md(text):
    chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f"\\{c}" if c in chars else c for c in text)

# ================= POPULAR FILTER =================
def is_popular(title, summary):
    text = f"{title} {summary}".lower()
    hits = sum(1 for k in POPULAR_KEYWORDS if k in text)
    return hits >= 1 and len(text) >= MIN_TEXT_LENGTH

# ================= IMAGE =================
def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

async def download_football_image():
    url = "https://source.unsplash.com/1200x675/?football,soccer,stadium"
    filename = f"{IMAGE_DIR}/{uuid.uuid4().hex}.jpg"

    async with aiohttp.ClientSession() as s:
        async with s.get(url, timeout=15) as r:
            if r.status == 200:
                with open(filename, "wb") as f:
                    f.write(await r.read())
                return filename
    return None

# ================= MESSAGE =================
def build_message(title, summary, source_name):
    accroche = random.choice(ACCROCHES)
    hashtags = " ".join(random.sample(HASHTAGS, 3))

    msg = (
        f"{accroche}*{clean_text(title, 90)}*\n\n"
        f"{clean_text(summary, 500)}\n\n"
        f"📰 *Source :* {source_name}\n"
        f"🕒 *Heure :* {datetime.now().strftime('%H:%M')}\n\n"
        f"{hashtags}"
    )
    return escape_md(msg)

# ================= TELEGRAM =================
async def post_with_comment(photo, message):
    for channel in CHANNELS:
        sent = None

        if photo.startswith("http"):
            sent = await bot.send_photo(channel, photo, caption=message, parse_mode="MarkdownV2")
        else:
            with open(photo, "rb") as f:
                sent = await bot.send_photo(channel, f, caption=message, parse_mode="MarkdownV2")

        await bot.send_message(
            channel,
            random.choice(COMMENTS),
            reply_to_message_id=sent.message_id
        )

        logger.info(f"✅ Post + commentaire publié sur {channel}")
        await asyncio.sleep(random.randint(8, 12))

# ================= LOOP =================
async def rss_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                for feed_url in RSS_FEEDS:
                    async with session.get(feed_url, timeout=20) as r:
                        feed = feedparser.parse(await r.text())

                        # Déterminer source par URL
                        if "lequipe" in feed_url:
                            source_name = SOURCE_NAMES["lequipe"]
                        elif "rmcsport" in feed_url:
                            source_name = SOURCE_NAMES["rmcsport"]
                        elif "goal" in feed_url:
                            source_name = SOURCE_NAMES["goal"]
                        else:
                            source_name = "Football FR"

                        for entry in feed.entries:
                            uid = entry.get("id") or entry.get("title")
                            if not uid or uid in posted_links:
                                continue

                            title = entry.get("title", "")
                            summary = entry.get("summary", "")

                            if not is_popular(title, summary):
                                continue

                            img = extract_image(entry)
                            temp = None

                            if not img:
                                temp = await download_football_image()

                            msg = build_message(title, summary, source_name)
                            await post_with_comment(img or temp, msg)

                            posted_links.add(uid)
                            save_posted()

                            if temp and os.path.exists(temp):
                                os.remove(temp)

                            await asyncio.sleep(random.randint(12, 18))

            except Exception as e:
                logger.error(f"❌ RSS error: {e}")

            await asyncio.sleep(600)  # Vérifie toutes les 10 min

# ================= MAIN =================
async def main():
    logger.info("🤖 Bot Football FR Multi-sources lancé")
    await rss_loop()

if __name__ == "__main__":
    asyncio.run(main())
