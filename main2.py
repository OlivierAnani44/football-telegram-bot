import os
import json
import logging
import random
import asyncio
import aiohttp
import feedparser
import re
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from bs4 import BeautifulSoup
from html import escape  # Échappe les caractères spéciaux HTML

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS")  # Séparés par des virgules
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

# Flux RSS films/séries francophones
RSS_FEEDS = [
    "https://www.allocine.fr/rss/news.xml",       # Actualités cinéma
    "https://www.seriesaddict.fr/rss/news.xml"   # Actualités séries
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
    'sortie': ['🎬', '🍿', '✨', '🎥'],
    'critique': ['⭐', '📝', '👍', '👎'],
    'bande_annonce': ['🎞️', '▶️', '📽️'],
    'casting': ['🎭', '👩‍🎤', '👨‍🎤'],
    'general': ['📰', '🔥', '🚀', '💥']
}

PHRASES_ACCROCHE = {
    'general': ["📰 INFO : ", "⚡ ACTU : ", "🔥 NOUVELLE : "]
}

HASHTAGS_FR = ["#Film", "#Série", "#Cinéma", "#Sortie", "#BandeAnnonce"]

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
    
    # Choix des accroches et emojis
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emojis = [random.choice(EMOJI_CATEGORIES.get(main_cat, ['📰']))]
    
    # Hashtags
    hashtags = ' '.join(random.sample(HASHTAGS_FR, min(5, len(HASHTAGS_FR))))
    
    # Partie principale (résumé complet avec introduction)
    main_part = (
        f"<b><i>{escape(clean_title)}</i></b>\n\n"
        f"<blockquote>{escape(clean_summary)}</blockquote>\n\n"
    )

    # Message final avec toutes les informations : titre, résumé, source, horaire, etc.
    message = (
        f"{''.join(emojis)} {accroche}\n\n"  # Emojis et accroche
        f"{main_part}"  # Partie principale avec titre et résumé
        f"📰 <b>Source :</b> <code>{escape(source or 'Média')}</code>\n"
        f"🕐 <b>Publié :</b> <code>{datetime.now().strftime('%H:%M')}</code>\n"
        f"📊 <b>Catégorie :</b> {main_cat.upper()}\n\n"
        f"{hashtags}"  # Hashtags
    )
    
    return message

# ---------------- IMAGE EXTRACTION ----------------
def extract_image(entry):
    # 1️⃣ Vérifie media_content ou media_thumbnail
    if 'media_content' in entry:
        return entry.media_content[0].get('url')
    if 'media_thumbnail' in entry:
        return entry.media_thumbnail[0].get('url')
    
    # 2️⃣ Sinon cherche la première image dans le summary/description
    summary = entry.get('summary', '') or entry.get('description', '')
    soup = BeautifulSoup(summary, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return img_tag['src']
    
    # 3️⃣ Pas d'image trouvée
    return None

# ---------------- POST NEWS ----------------
async def post_to_channels(photo_url, message):
    for channel in CHANNELS:
        try:
            if photo_url:
                await bot.send_photo(chat_id=channel, photo=photo_url, caption=message, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=channel, text=message, parse_mode="HTML")
            logger.info(f"✅ Publié sur {channel}")
        except TelegramError as e:
            logger.error(f"❌ Telegram error {channel}: {e}")
        await asyncio.sleep(random.randint(3, 6))

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
                            
                            # 📸 Extraction automatique de l
