# -*- coding: utf-8 -*-
import os
import json
import re
import asyncio
import logging
from datetime import datetime
from html import escape as html_escape
from telethon import TelegramClient, events
from googletrans import Translator

# ---------------- CONFIGURATION ----------------
API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

PRIVATE_CHANNEL = os.getenv("PRIVATE_CHANNEL")  # Canal privé
PUBLIC_CHANNELS = os.getenv("PUBLIC_CHANNELS").split(",")  # Liste des canaux publics

POSTED_FILE = "posted.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

translator = Translator()

# ---------------- EMOJIS, ACCROCHES, HASHTAGS ----------------
EMOJI_CATEGORIES = ['⚽','🏆','🔥','📰']
PHRASES_ACCROCHE = ["📰 INFO FOOT : ", "⚡ ACTU FOOT : ", "🔥 NOUVELLE FOOT : "]
HASHTAGS_FR = ["#Football", "#Foot", "#PremierLeague", "#Ligue1", "#SerieA"]

# ---------------- GESTION DES MESSAGES DÉJÀ PUBLIÉS ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f, ensure_ascii=False, indent=2)

posted_links = load_posted()

# ---------------- UTILITAIRES ----------------
def clean_text(text, max_len=500):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>','',text)
    text = re.sub(r'https?://\S+','',text)
    text = re.sub(r'\s+',' ',text).strip()
    if len(text) > max_len:
        text = text[:max_len]+"..."
    return text

def translate_text(text):
    try:
        text_str = "" if text is None else str(text)
        text_str = re.sub(r'<[^>]+>','',text_str)
        text_str = re.sub(r'https?://\S+','',text_str)
        text_str = re.sub(r'\s+',' ',text_str).strip()
        if not text_str:
            return ""
        return translator.translate(text_str, src='en', dest='fr').text
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text_str

def enrich_message(text):
    emoji = EMOJI_CATEGORIES[0]
    accroche = PHRASES_ACCROCHE[0]
    hashtags = " ".join(HASHTAGS_FR)
    heure = datetime.now().strftime('%H:%M')
    clean = html_escape(clean_text(text))
    message = f"""{emoji} <b>{accroche}{clean}</b>

🕐 <b>Publié :</b> <code>{heure}</code>

{hashtags}"""
    return message

# ---------------- TELETHON CLIENT ----------------
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

@client.on(events.NewMessage(chats=PRIVATE_CHANNEL))
async def handler(event):
    global posted_links

    text = event.message.message
    photo = None
    if event.message.media:
        photo = event.message.media

    if not text or text in posted_links:
        return

    posted_links.add(text)
    save_posted(posted_links)

    # Traduction
    text_fr = translate_text(text)
    enriched = enrich_message(text_fr)

    # Publication sur les canaux publics
    for ch in PUBLIC_CHANNELS:
        try:
            if photo:
                await client.send_file(ch.strip(), photo, caption=enriched, parse_mode='html')
            else:
                await client.send_message(ch.strip(), enriched, parse_mode='html')
            logger.info(f"✅ Publié sur {ch.strip()}")
        except Exception as e:
            logger.error(f"❌ Erreur publication sur {ch.strip()} : {e}")

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot privé -> public démarré")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
