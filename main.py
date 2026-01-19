import os
import asyncio
import logging
import re
from datetime import datetime
from html import escape as html_escape
from googletrans import Translator
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
PRIVATE_CHANNEL = os.getenv("PRIVATE_CHANNEL")  # Canal privé
PUBLIC_CHANNELS = os.getenv("PUBLIC_CHANNELS")  # Canal(s) public(s)
PUBLIC_CHANNELS = [ch.strip() for ch in PUBLIC_CHANNELS.split(",") if ch.strip()]

POSTED_FILE = "posted.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
translator = Translator()

# ---------------- EMOJIS, ACCROCHES, HASHTAGS ----------------
EMOJI_CATEGORIES = ['⚽','🏆','🔥','📰']
PHRASES_ACCROCHE = ["📰 INFO FOOT : ", "⚡ ACTU FOOT : ", "🔥 NOUVELLE FOOT : "]
HASHTAGS_FR = ["#Football", "#Foot", "#PremierLeague", "#Ligue1", "#SerieA"]

# ---------------- GESTION DES POSTS ----------------
import json
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE,"r",encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted):
    with open(POSTED_FILE,"w",encoding="utf-8") as f:
        json.dump(list(posted),f,ensure_ascii=False,indent=2)

posted_links = load_posted()

# ---------------- UTILITAIRES ----------------
def clean_text(text,max_len=500):
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

# ---------------- LECTURE DU CANAL PRIVÉ ET POST PUBLIC ----------------
async def check_private_channel():
    global posted_links
    last_id = None
    while True:
        try:
            updates = await bot.get_chat_history(chat_id=PRIVATE_CHANNEL, limit=10)
            for msg in reversed(updates):  # On lit du plus ancien au plus récent
                text = msg.text or ""
                if not text or text in posted_links:
                    continue
                posted_links.add(text)
                save_posted(posted_links)

                # Traduction
                text_fr = translate_text(text)
                enriched = enrich_message(text_fr)

                # Publication sur les canaux publics
                for ch in PUBLIC_CHANNELS:
                    try:
                        await bot.send_message(chat_id=ch, text=enriched, parse_mode="HTML")
                        logger.info(f"✅ Publié sur {ch}")
                    except TelegramError as e:
                        logger.error(f"❌ Telegram error {ch}: {e}")

        except Exception as e:
            logger.error(f"❌ Erreur lecture canal privé : {e}")

        await asyncio.sleep(10)  # Vérifie toutes les 10 secondes

# ---------------- MAIN ----------------
async def main():
    logger.info("🤖 Bot privé -> public démarré")
    await check_private_channel()

if __name__ == "__main__":
    if not BOT_TOKEN or not PRIVATE_CHANNEL or not PUBLIC_CHANNELS:
        logger.error("❌ BOT_TOKEN, PRIVATE_CHANNEL et PUBLIC_CHANNELS requis")
        exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
