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
from html import escape as html_escape

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS")  # Séparés par des virgules
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

RSS_FEEDS = [
    "https://www.allocine.fr/rss/news.xml"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

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

bot = Bot(token=BOT_TOKEN)

# ---------------- POSTÉ PAR CANAL ----------------
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # S'assurer que chaque channel est un set
                return {ch: set(links) for ch, links in data.items()}
    except Exception as e:
        logger.error(f"❌ Erreur chargement: {e}")
    return {ch: set() for ch in CHANNELS}

def save_posted_links():
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump({ch: list(links) for ch, links in posted_links.items()},
                      f, ensure_ascii=False, indent=2)
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

def escape_html(text: str) -> str:
    return html_escape(text)

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
    clean_summary = escape_html(clean_text(summary))
    clean_title = escape_html(clean_text(title, max_len=80))
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emoji = random.choice(EMOJI_CATEGORIES.get(main_cat, ['📰']))
    hashtags = ' '.join(HASHTAGS_FR)
    source_name = escape_html(source or "Média")
    heure = datetime.now().strftime('%H:%M')

    message = f"""
{emoji} <b>{accroche}{clean_title}</b>

<blockquote><i>{clean_summary}</i></blockquote>

📰 <b>Source :</b> <i>{source_name}</i>
🕐 <b>Publié :</b> <code>{heure}</code>
📊 <b>Catégorie :</b> <code>{main_cat.upper()}</code>

{hashtags}
""".strip()

    return message

def extract_image(entry):
    if 'media_content' in entry:
        return entry.media_content[0].get('url')
    if 'media_thumbnail' in entry:
        return entry.media_thumbnail[0].get('url')
    summary = entry.get('summary', '') or entry.get('description', '')
    soup = BeautifulSoup(summary, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return img_tag['src']
    return None

# ---------------- POST NEWS ----------------
async def post_to_channels(photo_url, message, button_url=None):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔘 Lire l'article", url=button_url)]]
    ) if button_url else None

    for channel in CHANNELS:
        if button_url in posted_links.get(channel, set()):
            logger.info(f"⏩ Déjà posté dans {channel}, passage au suivant")
            continue
        try:
            if photo_url:
                await bot.send_photo(
                    chat_id=channel,
                    photo=photo_url,
                    caption=message,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    chat_id=channel,
                    text=message,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            posted_links[channel].add(button_url)
            save_posted_links()
            logger.info(f"✅ Publié sur {channel}")
        except TelegramError as e:
            logger.error(f"❌ Telegram error {channel}: {e}")
        await asyncio.sleep(random.randint(3, 6))

# ---------------- RSS SCHEDULER ----------------
async def rss_scheduler():
    intervals = [600, 660, 420]  # 10min, 11min, 7min
    idx = 0

    async with aiohttp.ClientSession() as session:
        while True:
            for feed_url in RSS_FEEDS:
                try:
                    async with session.get(feed_url) as resp:
                        content = await resp.text()
                        feed = feedparser.parse(content)

                        for entry in feed.entries:
                            link = entry.get('link')
                            if not link:
                                continue

                            # ⚡ Vérifie si déjà posté dans tous les canaux
                            if all(link in posted_links.get(ch, set()) for ch in CHANNELS):
                                continue

                            title = entry.get('title', '')
                            summary = entry.get('summary', '') or entry.get('description', '')
                            img_url = extract_image(entry)
                            msg = generate_enriched_content(title, summary, feed.feed.get('title'))

                            await post_to_channels(img_url, msg, button_url=link)

                            # Intervalle variable entre posts
                            await asyncio.sleep(intervals[idx % len(intervals)])
                            idx += 1

                except Exception as e:
                    logger.error(f"❌ Erreur RSS {feed_url}: {e}")

            await asyncio.sleep(300)  # 5 min avant de relire le flux complet

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot Allociné démarré")
    await rss_scheduler()

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN et CHANNELS requis")
        exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
