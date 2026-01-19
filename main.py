import os
import feedparser
import sqlite3
import logging
import asyncio
import random
from datetime import datetime
from html import escape as html_escape
from googletrans import Translator
from telegram import Bot

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_CHANNELS = os.getenv("PUBLIC_CHANNELS", "")
PUBLIC_CHANNELS = [ch.strip() for ch in PUBLIC_CHANNELS.split(",") if ch.strip()]

RSS_FEEDS = ["https://feeds.bbci.co.uk/sport/football/rss.xml"]
DB_FILE = "messages.db"

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def store_rss_to_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.get("link")
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            text_en = f"{title}\n{summary}\n{link}"

            # Vérifie si déjà stocké
            c.execute("SELECT 1 FROM messages WHERE text_en LIKE ?", (f"%{link}%",))
            if c.fetchone():
                continue

            c.execute("INSERT INTO messages (text_en, image_url) VALUES (?, ?)", (text_en, None))
    
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
translator = Translator()
EMOJI_CATEGORIES = ['⚽','🏆','🔥','📰']
PHRASES_ACCROCHE = ["📰 INFO FOOT : ", "⚡ ACTU FOOT : ", "🔥 NOUVELLE FOOT : "]
HASHTAGS_FR = ["#Football", "#Foot", "#PremierLeague", "#Ligue1", "#SerieA"]

def clean_text(text, max_len=500):
    import re
    if not text:
        return ""
    text = re.sub(r'<[^>]+>','',text)
    text = re.sub(r'https?://\S+','',text)
    text = re.sub(r'\s+',' ',text).strip()
    return text[:max_len]+"..." if len(text) > max_len else text

def translate_text(text):
    try:
        return translator.translate(clean_text(text), src='en', dest='fr').text
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text

def enrich_message(text):
    emoji = random.choice(EMOJI_CATEGORIES)
    accroche = random.choice(PHRASES_ACCROCHE)
    hashtags = " ".join(HASHTAGS_FR)
    heure = datetime.now().strftime('%H:%M')
    clean = html_escape(clean_text(text))
    message = f"""{emoji} <b>{accroche}{clean}</b>

🕐 <b>Publié :</b> <code>{heure}</code>

{hashtags}"""
    return message

# ---------------- TELEGRAM ----------------
bot = Bot(token=BOT_TOKEN)

async def check_and_post():
    while True:
        messages = get_unposted_messages()
        if not messages:
            await asyncio.sleep(10)
            continue

        for msg_id, text_en, image_url in messages:
            text_fr = translate_text(text_en)
            enriched = enrich_message(text_fr)

            for ch in PUBLIC_CHANNELS:
                try:
                    if image_url:
                        bot.send_photo(chat_id=ch, photo=image_url, caption=enriched, parse_mode='HTML')
                    else:
                        bot.send_message(chat_id=ch, text=enriched, parse_mode='HTML')
                    logger.info(f"✅ Publié sur {ch}")
                except Exception as e:
                    logger.error(f"❌ Erreur publication sur {ch} : {e}")

            mark_posted(msg_id)
            await asyncio.sleep(3)

        await asyncio.sleep(5)

# ---------------- SCHEDULER ----------------
async def scheduler():
    while True:
        store_rss_to_db()   # Stocke le RSS dans SQLite
        await check_and_post()  # Publie sur Telegram
        await asyncio.sleep(300)  # toutes les 5 minutes

# ---------------- MAIN ----------------
async def main():
    init_db()
    logger.info("🤖 Bot Telegram RSS -> Public démarré")
    await scheduler()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
