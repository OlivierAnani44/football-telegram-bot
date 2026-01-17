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
from telegram.error import TelegramError
from bs4 import BeautifulSoup

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS", "")
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

RSS_FEEDS = [
    "https://cryptoast.fr/feed/",
    "https://journalducoin.com/feed/",
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]

POSTED_FILE = "posted.json"
IMAGE_DIR = "images"
MAX_POSTED = 3000

os.makedirs(IMAGE_DIR, exist_ok=True)

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("CRYPTOBOT")

bot = Bot(token=BOT_TOKEN)

# ================== STYLE ==================
EMOJIS = {
    "bitcoin": ["₿", "🚀", "🔥"],
    "ethereum": ["💎", "⚡"],
    "market": ["📊", "📈", "📉"],
    "regulation": ["⚖️", "🏛️"],
    "general": ["🪙", "📰"]
}

ACCROCHES = [
    "🪙 ACTU CRYPTO : ",
    "🔥 BREAKING : ",
    "📊 MARCHÉ : ",
    "🚀 TENDANCE : "
]

HASHTAGS = [
    "#Crypto", "#Bitcoin", "#Ethereum",
    "#Blockchain", "#Web3", "#Altcoins"
]

COMMENTS = [
    "💬 Qu’en pensez-vous ? Hausse ou chute à venir ?",
    "📊 Est-ce bullish ou bearish selon vous ?",
    "🤔 Bonne nouvelle ou risque pour le marché ?",
    "🔥 Impact réel sur le prix selon vous ?",
    "🪙 Votre avis nous intéresse 👇"
]

# ================== STORAGE ==================
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

# ================== TEXT ==================
def clean_text(text, max_len=600):
    if not text:
        return ""
    text = BeautifulSoup(text, "html.parser").get_text()
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text

def escape_md(text):
    chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f"\\{c}" if c in chars else c for c in text)

# ================== ANALYSE ==================
def analyze_crypto(title, summary):
    txt = f"{title} {summary}".lower()
    if "bitcoin" in txt or "btc" in txt:
        return "bitcoin"
    if "ethereum" in txt or "eth" in txt:
        return "ethereum"
    if any(w in txt for w in ["régulation", "loi", "sec", "gouvernement"]):
        return "regulation"
    if any(w in txt for w in ["marché", "prix", "chute", "hausse"]):
        return "market"
    return "general"

# ================== IMAGE ==================
def extract_image(entry):
    if 'media_content' in entry:
        return entry.media_content[0].get("url")
    html = entry.get("summary", "")
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

async def download_crypto_image(category):
    keywords = {
        "bitcoin": "bitcoin crypto",
        "ethereum": "ethereum blockchain",
        "market": "crypto market chart",
        "regulation": "cryptocurrency regulation",
        "general": "cryptocurrency blockchain"
    }

    query = keywords.get(category, "cryptocurrency")
    url = f"https://source.unsplash.com/1200x675/?{query.replace(' ', ',')}"
    filename = f"{IMAGE_DIR}/{uuid.uuid4().hex}.jpg"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as r:
                if r.status == 200:
                    with open(filename, "wb") as f:
                        f.write(await r.read())
                    return filename
    except Exception as e:
        logger.error(f"❌ Image auto: {e}")

    return None

# ================== MESSAGE ==================
def build_message(title, summary, source):
    cat = analyze_crypto(title, summary)
    emoji = random.choice(EMOJIS.get(cat, ["🪙"]))
    accroche = random.choice(ACCROCHES)
    hashtags = " ".join(random.sample(HASHTAGS, 4))

    msg = (
        f"{emoji} {accroche}*{clean_text(title, 80)}*\n\n"
        f"{clean_text(summary)}\n\n"
        f"📰 *Source :* {source}\n"
        f"🕒 *Heure :* {datetime.now().strftime('%H:%M')}\n"
        f"📌 *Catégorie :* {cat.upper()}\n\n"
        f"{hashtags}"
    )
    return escape_md(msg), cat

# ================== TELEGRAM ==================
async def post_with_comment(photo, message):
    for channel in CHANNELS:
        try:
            # 🔹 Post principal
            if photo:
                if photo.startswith("http"):
                    sent = await bot.send_photo(
                        channel, photo,
                        caption=message,
                        parse_mode="MarkdownV2"
                    )
                else:
                    with open(photo, "rb") as f:
                        sent = await bot.send_photo(
                            channel, f,
                            caption=message,
                            parse_mode="MarkdownV2"
                        )
            else:
                sent = await bot.send_message(
                    channel, message,
                    parse_mode="MarkdownV2"
                )

            # 🔹 Commentaire automatique
            comment = random.choice(COMMENTS)
            try:
                await bot.send_message(
                    channel,
                    comment,
                    reply_to_message_id=sent.message_id
                )
            except TelegramError:
                await bot.send_message(channel, comment)

            logger.info(f"✅ Publié + commentaire sur {channel}")

        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")

        await asyncio.sleep(random.randint(5, 8))

# ================== LOOP ==================
async def rss_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            for feed_url in RSS_FEEDS:
                try:
                    async with session.get(feed_url, timeout=20) as r:
                        feed = feedparser.parse(await r.text())

                        for entry in feed.entries:
                            uid = entry.get("id") or entry.get("title")
                            if not uid or uid in posted_links:
                                continue

                            msg, category = build_message(
                                entry.get("title", ""),
                                entry.get("summary", ""),
                                feed.feed.get("title", "Crypto Media")
                            )

                            img = extract_image(entry)
                            temp_img = None
                            if not img:
                                temp_img = await download_crypto_image(category)

                            await post_with_comment(img or temp_img, msg)

                            posted_links.add(uid)
                            save_posted()

                            if temp_img and os.path.exists(temp_img):
                                os.remove(temp_img)

                            await asyncio.sleep(random.randint(8, 14))

                except Exception as e:
                    logger.error(f"❌ RSS error: {e}")

            await asyncio.sleep(900)

# ================== MAIN ==================
async def main():
    logger.info("🤖 Bot ACTU CRYPTO avec commentaires lancé")
    await rss_loop()

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN ou CHANNELS manquant")
        exit(1)
    asyncio.run(main())
