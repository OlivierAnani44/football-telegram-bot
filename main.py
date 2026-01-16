import os
import feedparser
import json
import asyncio
import logging
import re
import random
import hashlib
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from bs4 import BeautifulSoup

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_IDS = [c.strip() for c in os.getenv("CHANNEL_IDS", "").split(",") if c.strip()]

POSTED_FILE = "posted.json"
MAX_POSTED = 2500
DEFAULT_IMAGE = "https://i.imgur.com/8YqG4xk.jpg"

PROMO_CHANNEL_URL = "https://t.me/mrxpronosfr"

PROMO_MESSAGE = """🚫 Arrêté d'acheter les C0UP0NS qui vont perdre tous le temps 🚫

Un bon pronostiqueur ne vend rien s’il gagne vraiment ✅  
Venez prendre les C0UP0NS GRATUITEMENT ✅ tous les jours dans ce CANAL TELEGRAM 🌐  
Fiable à 90%
"""

RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://rmcsport.bfmtv.com/rss/football/",
    "https://www.eurosport.fr/football/rss.xml",
    "https://www.footmercato.net/rss",
    "https://www.maxifoot.fr/rss.xml",
    "https://www.leparisien.fr/sports/football/rss.xml",
    "https://www.france24.com/fr/sports/football/rss",
]

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("FootballBot")

bot = Bot(token=BOT_TOKEN)

# ================= UTILS =================
def escape_md(text):
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', text or "")

def clean_text(text, max_len=500):
    text = re.sub(r'<[^>]+>', '', text or "")
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text

def hash_article(title, link):
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()

# ================= STORAGE =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f, ensure_ascii=False, indent=2)

posted = load_posted()

# ================= IMAGE =================
def extract_image(entry):
    if hasattr(entry, "media_content"):
        for m in entry.media_content:
            if m.get("url"):
                return m["url"]
    if hasattr(entry, "media_thumbnail"):
        return entry.media_thumbnail[0].get("url")
    if hasattr(entry, "summary"):
        soup = BeautifulSoup(entry.summary, "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]
    return DEFAULT_IMAGE

# ================= CONTENT =================
def build_message(title, summary, source):
    title = escape_md(clean_text(title, 80))
    summary = escape_md(clean_text(summary, 350))
    source = escape_md(source)

    return f"""⚽ *ACTUALITÉ FOOTBALL*

*{title}*

{summary}

📰 *Source* : {source}
🕒 *{datetime.utcnow().strftime('%H:%M')} UTC*

#Football #Foot
"""

# ================= PROMO =================
async def send_promo_message():
    logger.info("📢 Envoi message promotionnel")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 Rejoindre le canal", url=PROMO_CHANNEL_URL)]
    ])

    for channel in CHANNEL_IDS:
        try:
            await bot.send_message(
                chat_id=channel,
                text=PROMO_MESSAGE,
                reply_markup=keyboard
            )
        except TelegramError as e:
            logger.error(f"Erreur promo {channel}: {e}")

# ================= NEWS =================
async def check_news():
    new_posts = 0

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        if feed.bozo or not feed.entries:
            continue

        for entry in feed.entries[:3]:
            if not hasattr(entry, "link"):
                continue

            uid = hash_article(entry.title, entry.link)
            if uid in posted:
                continue

            image = extract_image(entry)
            message = build_message(
                entry.title,
                getattr(entry, "summary", entry.title),
                feed.feed.get("title", "Média")
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔘 Lire l’article", url=entry.link)]
            ])

            for channel in CHANNEL_IDS:
                try:
                    await bot.send_photo(
                        chat_id=channel,
                        photo=image,
                        caption=message,
                        parse_mode="MarkdownV2",
                        reply_markup=keyboard
                    )
                except TelegramError as e:
                    logger.error(f"Telegram error: {e}")

            posted.add(uid)
            new_posts += 1
            await asyncio.sleep(15)

    if new_posts:
        save_posted()

    return new_posts

# ================= MAIN LOOP =================
async def main():
    logger.info("🤖 Bot Football + Promo démarré")

    last_day = None
    promo_morning = False
    promo_evening = False

    while True:
        try:
            now = datetime.utcnow()
            today = now.date()

            if today != last_day:
                promo_morning = False
                promo_evening = False
                last_day = today

            # 09h UTC
            if now.hour == 9 and not promo_morning:
                await send_promo_message()
                promo_morning = True

            # 18h UTC
            if now.hour == 18 and not promo_evening:
                await send_promo_message()
                promo_evening = True

            await check_news()
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Erreur boucle principale: {e}")
            await asyncio.sleep(60)

# ================= START =================
if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNEL_IDS:
        logger.error("❌ BOT_TOKEN ou CHANNEL_IDS manquant")
        exit(1)

    asyncio.run(main())
