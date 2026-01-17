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

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

RSS_FEEDS = [
    "https://www.allocine.fr/rss/news.xml",       # Actualités cinéma
    "https://www.seriesaddict.fr/rss/news.xml"   # Actualités séries
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------- EMOJIS / PHRASES ----------------
EMOJI_CATEGORIES = {
    'sortie': ['🎬', '🍿', '✨', '🎥'],
    'critique': ['⭐', '📝', '👍', '👎'],
    'bande_annonce': ['🎞️', '▶️', '📽️'],
    'casting': ['🎭', '👩‍🎤', '👨‍🎤'],
    'general': ['📰', '🔥', '🚀', '💥']
}

PHRASES_ACCROCHE = {
    'general': ["📰 INFO : ", "⚡ ACTU : ", "🔥 NOUVELLE : "],
    'sortie': ["🍿 Nouvelle sortie : ", "🎬 À l'affiche : "],
    'critique': ["⭐ Critique : ", "📝 Avis : "],
    'bande_annonce': ["▶️ Bande-annonce : ", "🎞️ Trailer : "],
    'casting': ["🎭 Casting : ", "👩‍🎤👨‍🎤 Annonce : "]
}

HASHTAGS_FR = ["#Film", "#Série", "#Cinéma", "#Sortie", "#BandeAnnonce"]

# ---------------- BOT ----------------
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

# ---------------- ANALYSE ----------------
def analyze_content(title, summary):
    text = f"{title} {summary}".lower()
    if any(word in text for word in ["sortie", "film", "série", "cinéma"]):
        return 'sortie'
    if any(word in text for word in ["critique", "avis", "review"]):
        return 'critique'
    if any(word in text for word in ["bande-annonce", "trailer"]):
        return 'bande_annonce'
    if any(word in text for word in ["casting", "acteur", "actrice"]):
        return 'casting'
    return 'general'

def generate_enriched_content(title, summary, source):
    main_cat = analyze_content(title, summary)
    clean_summary = clean_text(summary, max_len=400)
    clean_title = clean_text(title, max_len=80)
    
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emojis = [random.choice(EMOJI_CATEGORIES.get(main_cat, ['📰']))]
    
    hashtags = ' '.join(random.sample(HASHTAGS_FR, min(5, len(HASHTAGS_FR))))
    
    main_part = (
        f"<b><i>{escape(clean_title)}</i></b>\n\n"
        f"<blockquote>{escape(clean_summary)}</blockquote>\n\n"
    )

    message = (
        f"{''.join(emojis)} {accroche}\n\n"
        f"{main_part}"
        f"📰 <b>Source :</b> <code>{escape(source or 'Média')}</code>\n"
        f"🕐 <b>Publié :</b> <code>{datetime.now().strftime('%H:%M')}</code>\n"
        f"📊 <b>Catégorie :</b> {main_cat.upper()}\n\n"
        f"{hashtags}"
    )
    
    return message

# ---------------- IMAGE ----------------
def extract_image(entry):
    if 'media_content' in entry:
        return entry.media_content[0].get('url')
    if 'media_thumbnail' in entry:
        return entry.media_thumbnail[0].get('url')
    summary = entry.get('summary', '') or entry.get('description', '')
    soup = BeautifulSoup(summary, 'html.parser')
    img_tag = soup.find('img')
    return img_tag['src'] if img_tag else None

# ---------------- POST ----------------
async def post_to_channels(message, photo_url=None):
    for channel in CHANNELS:
        try:
            if photo_url:
                await bot.send_photo(chat_id=channel, photo=photo_url, caption=message, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(chat_id=channel, text=message, parse_mode=ParseMode.HTML)
            logger.info(f"✅ Publié sur {channel}")
        except Exception as e:
            logger.error(f"❌ Telegram error {channel}: {e}")
        await asyncio.sleep(random.randint(3,6))

# ---------------- RSS SCHEDULER ----------------
async def fetch_feed(session, url):
    async with session.get(url) as resp:
        content = await resp.text()
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, lambda: feedparser.parse(content))
        return feed

async def rss_scheduler():
    async with aiohttp.ClientSession() as session:
        while True:
            for feed_url in RSS_FEEDS:
                try:
                    feed = await fetch_feed(session, feed_url)
                    for entry in feed.entries:
                        link = entry.get('link')
                        if not link or link in posted_links:
                            continue
                        title = entry.get('title', '')
                        summary = entry.get('summary', '') or entry.get('description', '')
                        img_url = extract_image(entry)
                        msg = generate_enriched_content(title, summary, feed.feed.get('title'))
                        await post_to_channels(msg, img_url)
                        posted_links.add(link)
                        save_posted_links()
                        # On attend 5 minutes minimum avant le prochain post
                        await asyncio.sleep(300)
                except Exception as e:
                    logger.error(f"❌ Erreur RSS {feed_url}: {e}")
            # On attend 5 minutes avant de re-vérifier tous les flux
            await asyncio.sleep(300)


# ---------------- MAIN ----------------
if __name__ == "__main__":
    asyncio.run(rss_scheduler())
