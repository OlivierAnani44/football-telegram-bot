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
from html import escape as html_escape
import aiohttp
from deep_translator import DeeplTranslator

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS")  # Séparés par des virgules
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

POSTED_FILE = "posted.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ---------------- EMOJIS, ACCROCHES, HASHTAGS ----------------
EMOJI_CATEGORIES = {
    'match': ['⚽', '🏆', '🔥', '🎯'],
    'transfert': ['🔄', '💰', '👤'],
    'résultat': ['🏅', '📊', '⚡'],
    'general': ['📰', '🔥', '🚀', '💥']
}

PHRASES_ACCROCHE = {
    'general': ["📰 INFO FOOT : ", "⚡ ACTU FOOT : ", "🔥 NOUVELLE FOOT : "]
}

HASHTAGS_FR = ["#Football", "#Foot", "#PremierLeague", "#Ligue1", "#SerieA"]

bot = Bot(token=BOT_TOKEN)

# ---------------- GESTION DES LIENS DÉJÀ POSTÉS ----------------
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
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
def clean_text(text, max_len=1000):
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

# ---------------- TRADUCTION ----------------
def translate_text(text: str) -> str:
    try:
        return DeeplTranslator(source='en', target='fr').translate(text)
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text

# ---------------- ANALYSE CATEGORIE ----------------
def analyze_content(title, summary):
    text = f"{title} {summary}".lower()
    if any(word in text for word in ["match", "score", "victoire", "défaite"]):
        return 'match'
    if any(word in text for word in ["transfert", "signature", "contrat"]):
        return 'transfert'
    if any(word in text for word in ["résultat", "score"]):
        return 'résultat'
    return 'general'

# ---------------- GENERATION MESSAGE ----------------
def generate_enriched_content(title, summary, source):
    # Traduction complète
    title_fr = translate_text(title)
    summary_fr = translate_text(summary)

    main_cat = analyze_content(title_fr, summary_fr)
    clean_summary = escape_html(clean_text(summary_fr))
    clean_title = escape_html(clean_text(title_fr, max_len=80))
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emoji = random.choice(EMOJI_CATEGORIES.get(main_cat, ['📰']))
    hashtags = ' '.join(HASHTAGS_FR)
    source_name = escape_html(source or "BBC Sport")
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

# ---------------- EXTRACTION IMAGE ----------------
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

# ---------------- POST SUR TELEGRAM ----------------
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

# ---------------- SCHEDULER ----------------
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

                            if all(link in posted_links.get(ch, set()) for ch in CHANNELS):
                                continue

                            title = entry.get('title', '')
                            summary = entry.get('summary', '') or entry.get('description', '')
                            img_url = extract_image(entry)
                            msg = generate_enriched_content(title, summary, feed.feed.get('title'))

                            await post_to_channels(img_url, msg, button_url=link)
                            await asyncio.sleep(intervals[idx % len(intervals)])
                            idx += 1

                except Exception as e:
                    logger.error(f"❌ Erreur RSS {feed_url}: {e}")

            await asyncio.sleep(300)

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot BBC Football FR démarré")
    await rss_scheduler()

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN et CHANNELS requis")
        exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
