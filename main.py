# -*- coding: utf-8 -*-
import os
import sqlite3
import asyncio
import logging
from datetime import datetime
from html import escape as html_escape
from telethon import TelegramClient, events
from googletrans import Translator

# ---------------- CONFIGURATION ----------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_CHANNELS = os.getenv("PUBLIC_CHANNELS")

# Vérification des variables d'environnement
missing = []
if not API_ID: missing.append("API_ID")
if not API_HASH: missing.append("API_HASH")
if not BOT_TOKEN: missing.append("BOT_TOKEN")
if not PUBLIC_CHANNELS: missing.append("PUBLIC_CHANNELS")
if missing:
    raise ValueError(f"❌ Les variables suivantes sont manquantes : {', '.join(missing)}")

API_ID = int(API_ID)
PUBLIC_CHANNELS = [ch.strip() for ch in PUBLIC_CHANNELS.split(",") if ch.strip()]

DB_FILE = "messages.db"

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------- INITIALISATIONS ----------------
translator = Translator()
EMOJI_CATEGORIES = ['⚽','🏆','🔥','📰']
PHRASES_ACCROCHE = ["📰 INFO FOOT : ", "⚡ ACTU FOOT : ", "🔥 NOUVELLE FOOT : "]
HASHTAGS_FR = ["#Football", "#Foot", "#PremierLeague", "#Ligue1", "#SerieA"]

# ---------------- SQLITE ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text_en TEXT NOT NULL,
            image_url TEXT,
            posted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_unposted_messages():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, text_en, image_url FROM messages WHERE posted=0 ORDER BY created_at ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def mark_posted(msg_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE messages SET posted=1 WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()

# ---------------- UTILITAIRES ----------------
def clean_text(text, max_len=500):
    if not text:
        return ""
    import re
    text = re.sub(r'<[^>]+>','',text)
    text = re.sub(r'https?://\S+','',text)
    text = re.sub(r'\s+',' ',text).strip()
    if len(text) > max_len:
        text = text[:max_len]+"..."
    return text

def translate_text(text):
    try:
        text_str = "" if text is None else str(text)
        text_str = clean_text(text_str)
        if not text_str:
            return ""
        return translator.translate(text_str, src='en', dest='fr').text
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text

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

# ---------------- TELEGRAM CLIENT ----------------
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

async def check_and_post():
    while True:
        messages = get_unposted_messages()
        if not messages:
            await asyncio.sleep(30)  # attendre 30s si rien de nouveau
            continue

        for msg_id, text_en, image_url in messages:
            # Traduction et enrichissement
            text_fr = translate_text(text_en)
            enriched = enrich_message(text_fr)

            # Publication sur les canaux publics
            for ch in PUBLIC_CHANNELS:
                try:
                    if image_url:
                        await client.send_file(ch, image_url, caption=enriched, parse_mode='html')
                    else:
                        await client.send_message(ch, enriched, parse_mode='html')
                    logger.info(f"✅ Publié sur {ch}")
                except Exception as e:
                    logger.error(f"❌ Erreur publication sur {ch} : {e}")

            mark_posted(msg_id)
            await asyncio.sleep(5)  # éviter flood

        await asyncio.sleep(10)  # pause avant la prochaine vérification

# ---------------- MAIN ----------------
async def main():
    init_db()
    logger.info("🤖 Bot base SQLite démarré")
    await check_and_post()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
