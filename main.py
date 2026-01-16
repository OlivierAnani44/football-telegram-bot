import os
import feedparser
import json
import asyncio
import logging
import re
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from bs4 import BeautifulSoup
import random
from datetime import datetime
import aiohttp

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS")  # Séparés par des virgules, ex: @channel1,@channel2
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

# Flux RSS francophones (Seulement Lequipe et Footmercato)
RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://www.footmercato.net/rss"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Emojis et phrases
EMOJI_CATEGORIES = {
    'match': ['⚽', '🏆', '🆚', '🥅', '👕'],
    'transfert': ['🔄', '✍️', '📝', '💼', '💰'],
    'blessure': ['🤕', '🏥', '⚠️', '😔'],
    'championnat': ['🏅', '⭐', '👑', '🥇'],
    'general': ['📰', '🔥', '🚀', '💥']
}

PHRASES_ACCROCHE = {
    'general': ["📰 INFO : ", "⚡ ACTU : ", "🔥 NOUVELLE : "]
}

HASHTAGS_FR = ["#Foot", "#Football", "#Ligue1", "#LigueDesChampions", "#Mercato"]

# Bot
bot = Bot(token=BOT_TOKEN)

# ---------------- POSTÉ ----------------
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                links = set(json.load(f))
                if len(links) > MAX_POSTED_LINKS:
                    links = set(list(links)[-MAX_POSTED_LINKS:])
                logger.info(f"📁 {len(links)} liens chargés")
                return links
    except Exception as e:
        logger.error(f"❌ Erreur chargement: {e}")
    return set()

def save_posted_links():
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_links), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")

posted_links = load_posted_links()

# ---------------- UTILITAIRES ----------------
def clean_text(text, max_len=500):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text

def escape_markdown(text: str) -> str:
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)

# ---------------- ANALYSE ----------------
def analyze_content(title, summary):
    text = f"{title} {summary}".lower()
    if any(word in text for word in ["match", "score", "but"]):
        return 'match'
    if any(word in text for word in ["transfert", "mercato"]):
        return 'transfert'
    if any(word in text for word in ["blessure", "indisponible"]):
        return 'blessure'
    return 'general'

def generate_enriched_content(title, summary, source):
    main_cat = analyze_content(title, summary)
    clean_summary = clean_text(summary)
    clean_title = clean_text(title, max_len=80)
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emojis = [random.choice(EMOJI_CATEGORIES.get(main_cat, ['📰']))]
    hashtags = ' '.join(random.sample(HASHTAGS_FR, min(5, len(HASHTAGS_FR))))
    source_name = source or "Média"
    message = (
        f"{''.join(emojis)} {accroche}*{clean_title}*\n\n"
        f"{clean_summary}\n\n"
        f"📰 *Source :* {source_name}\n"
        f"🕐 *Publié :* {datetime.now().strftime('%H:%M')}\n"
        f"📊 *Catégorie :* {main_cat.upper()}\n\n"
        f"{hashtags}"
    )
    return escape_markdown(message)

# ---------------- POST NEWS ----------------
async def post_to_channels(photo_url, message, button_url=None):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔘 Lire l'article", url=button_url)]]) if button_url else None
    for channel in CHANNELS:
        try:
            if photo_url:
                await bot.send_photo(chat_id=channel, photo=photo_url, caption=message, parse_mode="MarkdownV2", reply_markup=keyboard)
            else:
                await bot.send_message(chat_id=channel, text=message, parse_mode="MarkdownV2", reply_markup=keyboard)
            logger.info(f"✅ Publié sur {channel}")
        except TelegramError as e:
            logger.error(f"❌ Telegram error {channel}: {e}")
        await asyncio.sleep(random.randint(3,6))

# ---------------- RSS SCHEDULER ----------------
async def rss_scheduler():
    async with aiohttp.ClientSession() as session:
        while True:
            for feed_url in RSS_FEEDS:
                try:
                    async with session.get(feed_url) as resp:
                        content = await resp.text()
                        feed = feedparser.parse(content)
                        for entry in feed.entries:
                            link = entry.get('link')
                            if not link or link in posted_links:
                                continue
                            title = entry.get('title', '')
                            summary = entry.get('summary', '') or entry.get('description', '')
                            # Image extraction
                            img_url = None
                            if 'media_content' in entry:
                                img_url = entry.media_content[0].get('url')
                            elif 'media_thumbnail' in entry:
                                img_url = entry.media_thumbnail[0].get('url')
                            msg = generate_enriched_content(title, summary, feed.feed.get('title'))
                            await post_to_channels(img_url, msg, button_url=link)
                            posted_links.add(link)
                            save_posted_links()
                            await asyncio.sleep(random.randint(5,10))
                except Exception as e:
                    logger.error(f"❌ Erreur RSS {feed_url}: {e}")
            await asyncio.sleep(900)  # Toutes les 15 minutes

# ---------------- PROMO ----------------
PROMO_MESSAGE = (
    "🚫 Arrêté d'acheter les C0UP0NS qui vont perdre tous le temps🚫, "
    "un bon pronostiqueur ne vend rien si effectivement il gagne✅, "
    "Venez prendre les C0UP0NS GRATUITEMENT✅ tout les jours dans ce CANAL TELEGRAM🌐 fiable à 90%\n\n"
    "🔵Lien du CANAL : https://t.me/mrxpronosfr"
)

async def send_promo():
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔘 Rejoindre le canal", url="https://t.me/mrxpronosfr")]])
    for channel in CHANNELS:
        try:
            await bot.send_message(chat_id=channel, text=escape_markdown(PROMO_MESSAGE), parse_mode="MarkdownV2", reply_markup=keyboard)
            logger.info(f"📢 Envoi message promo à {channel}")
        except TelegramError as e:
            logger.error(f"❌ Erreur promo {channel}: {e}")

async def promo_scheduler():
    while True:
        await send_promo()
        await asyncio.sleep(12*60*60)  # 12h

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot Football + Promo démarré")
    await asyncio.gather(
        rss_scheduler(),
        promo_scheduler()
    )

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN et CHANNELS requis")
        exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
