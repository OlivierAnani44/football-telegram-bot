import os
import feedparser
import json
import asyncio
import logging
import re
from telegram import Bot
from telegram.error import TelegramError
from bs4 import BeautifulSoup
import random
from datetime import datetime
import aiohttp

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS")  # séparés par virgules
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

# 🔥 Flux RSS CRYPTO
RSS_FEEDS = [
    "https://cryptoast.fr/feed/",
    "https://journalducoin.com/feed/",
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 3000

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------- EMOJIS & TEXTES ----------------
EMOJI_CATEGORIES = {
    "bitcoin": ["₿", "🚀", "🔥"],
    "ethereum": ["💎", "⚡", "🔥"],
    "regulation": ["⚖️", "🏛️"],
    "market": ["📉", "📈", "💰"],
    "general": ["🪙", "📰", "🚀"]
}

PHRASES_ACCROCHE = [
    "🪙 ACTU CRYPTO : ",
    "🔥 BREAKING : ",
    "📊 MARCHÉ : ",
    "🚀 TENDANCE : "
]

HASHTAGS = [
    "#Crypto",
    "#Bitcoin",
    "#Ethereum",
    "#Blockchain",
    "#Web3",
    "#Altcoins"
]

bot = Bot(token=BOT_TOKEN)

# ---------------- POSTED LINKS ----------------
def load_posted_links():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_posted_links():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links), f, indent=2, ensure_ascii=False)

posted_links = load_posted_links()

# ---------------- CLEAN TEXT ----------------
def clean_text(text, max_len=600):
    if not text:
        return ""
    text = BeautifulSoup(text, "html.parser").get_text()
    text = re.sub(r'https?://\S+', '', text)   # SUPPRESSION LIENS
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text

def escape_markdown(text):
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)

# ---------------- ANALYSE CONTENU ----------------
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

# ---------------- MESSAGE ----------------
def generate_message(title, summary, source):
    cat = analyze_crypto(title, summary)
    emoji = random.choice(EMOJI_CATEGORIES.get(cat, ["🪙"]))
    accroche = random.choice(PHRASES_ACCROCHE)
    hashtags = " ".join(random.sample(HASHTAGS, 4))

    message = (
        f"{emoji} {accroche}*{clean_text(title, 80)}*\n\n"
        f"{clean_text(summary)}\n\n"
        f"📰 *Source :* {source}\n"
        f"🕒 *Heure :* {datetime.now().strftime('%H:%M')}\n"
        f"📌 *Catégorie :* {cat.upper()}\n\n"
        f"{hashtags}"
    )
    return escape_markdown(message)

# ---------------- IMAGE ----------------
def extract_image(entry):
    if 'media_content' in entry:
        return entry.media_content[0].get('url')
    summary = entry.get('summary', '')
    soup = BeautifulSoup(summary, 'html.parser')
    img = soup.find('img')
    return img['src'] if img else None

# ---------------- POST ----------------
async def post_to_channels(photo, message):
    for channel in CHANNELS:
        try:
            if photo:
                await bot.send_photo(channel, photo, caption=message, parse_mode="MarkdownV2")
            else:
                await bot.send_message(channel, message, parse_mode="MarkdownV2")
            logger.info(f"✅ Publié sur {channel}")
        except TelegramError as e:
            logger.error(f"❌ {e}")
        await asyncio.sleep(random.randint(4, 7))

# ---------------- RSS LOOP ----------------
async def rss_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            for feed_url in RSS_FEEDS:
                try:
                    async with session.get(feed_url, timeout=20) as r:
                        feed = feedparser.parse(await r.text())
                        for entry in feed.entries:
                            uid = entry.get("id") or entry.get("title")
                            if uid in posted_links:
                                continue

                            msg = generate_message(
                                entry.get("title", ""),
                                entry.get("summary", ""),
                                feed.feed.get("title", "Crypto Media")
                            )

                            img = extract_image(entry)
                            await post_to_channels(img, msg)

                            posted_links.add(uid)
                            save_posted_links()
                            await asyncio.sleep(random.randint(6, 12))

                except Exception as e:
                    logger.error(f"❌ RSS error {feed_url}: {e}")

            await asyncio.sleep(900)

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot ACTU CRYPTO démarré")
    await rss_loop()

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN ou CHANNELS manquant")
        exit(1)
    asyncio.run(main())
