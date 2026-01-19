# -*- coding: utf-8 -*-
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
from googletrans import Translator  # Traducteur gratuit Google

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_CHANNEL = os.getenv("PRIVATE_CHANNEL")  # Canal privé pour brouillon
PUBLIC_CHANNELS = os.getenv("PUBLIC_CHANNELS")  # Canal(s) public(s)
PUBLIC_CHANNELS = [ch.strip() for ch in PUBLIC_CHANNELS.split(",") if ch.strip()]

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
translator = Translator()

# ---------------- GESTION DES LIENS DÉJÀ POSTÉS ----------------
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {ch: set(links) for ch, links in data.items()}
    except Exception as e:
        logger.error(f"❌ Erreur chargement: {e}")
    return {ch: set() for ch in PUBLIC_CHANNELS + [PRIVATE_CHANNEL]}

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

def translate_text(text: str) -> str:
    try:
        return translator.translate(text, src='en', dest='fr').text
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text

def analyze_content(title, summary):
    text = f"{title} {summary}".lower()
    if any(word in text for word in ["match", "score", "victoire", "défaite"]):
        return 'match'
    if any(word in text for word in ["transfert", "signature", "contrat"]):
        return 'transfert'
    if any(word in text for word in ["résultat", "score"]):
        return 'résultat'
    return 'general'

def generate_enriched_content(title, summary, source):
    title_fr = translate_text(title)
    summary_fr = translate_text(summary)
    main_cat = analyze_content(title_fr, summary_fr)
    clean_summary = html_escape(clean_text(summary_fr))
    clean_title = html_escape(clean_text(title_fr, max_len=80))
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emoji = random.choice(EMOJI_CATEGORIES.get(main_cat, ['📰']))
    hashtags = ' '.join(HASHTAGS_FR)
    source_name = html_escape(source or "BBC Sport")
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

# ---------------- POST SUR TELEGRAM ----------------
async def post_to_channel(channel, message, photo_url=None, button_url=None, raw=False):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔘 Lire l'article", url=button_url)]]
    ) if button_url and not raw else None

    if message in posted_links.get(channel, set()):
        logger.info(f"⏩ Déjà posté dans {channel}, passage")
        return

    try:
        if photo_url and not raw:
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
                parse_mode=None if raw else "HTML",
                reply_markup=keyboard
            )
        posted_links.setdefault(channel, set()).add(message if raw else button_url)
        save_posted_links()
        logger.info(f"✅ Publié sur {channel}")
    except TelegramError as e:
        logger.error(f"❌ Telegram error {channel}: {e}")

# ---------------- LOGIQUE BOT ----------------
async def rss_fetcher():
    intervals = [600, 660, 420]  # 10, 11, 7 min
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
                            if link in posted_links.get(PRIVATE_CHANNEL, set()):
                                continue

                            # --- POST BRUT DANS LE CANAL PRIVÉ ---
                            title = entry.get('title', '')
                            summary = entry.get('summary', '') or entry.get('description', '')
                            raw_message = f"{title}\n\n{summary}"
                            await post_to_channel(PRIVATE_CHANNEL, raw_message, raw=True)

                            # --- POST TRAITÉ DANS LES CANAUX PUBLICS ---
                            img_url = extract_image(entry)
                            enriched_msg = generate_enriched_content(title, summary, feed.feed.get('title'))
                            for ch in PUBLIC_CHANNELS:
                                await post_to_channel(ch, enriched_msg, photo_url=img_url, button_url=link)

                            await asyncio.sleep(intervals[idx % len(intervals)])
                            idx += 1

                except Exception as e:
                    logger.error(f"❌ Erreur RSS {feed_url}: {e}")

            await asyncio.sleep(300)

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot BBC Football FR démarré")
    await rss_fetcher()

if __name__ == "__main__":
    if not BOT_TOKEN or not PRIVATE_CHANNEL or not PUBLIC_CHANNELS:
        logger.error("❌ BOT_TOKEN, PRIVATE_CHANNEL et PUBLIC_CHANNELS requis")
        exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
