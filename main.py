import os
import logging
from deep_translator import LibreTranslator
from telegram import Bot

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Ton token Telegram
CHANNELS = ["@mrxpronos_actu", "@footinfo_vf_fr"]  # Tes canaux
SOURCE_TEXT = os.getenv("SOURCE_TEXT", "")  # Texte à traduire depuis variable

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

def translate_text(text: str) -> str:
    try:
        translated = LibreTranslator(source='en', target='fr').translate(text)
        return translated
    except Exception as e:
        logger.error(f"❌ Erreur traduction : {e}")
        return text  # Retourne le texte original en cas d'erreur

def post_to_channels(text: str):
    for ch in CHANNELS:
        try:
            bot.send_message(chat_id=ch, text=text, parse_mode='HTML')
            logger.info(f"✅ Publié sur {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur publication sur {ch} : {e}")

def main():
    if not SOURCE_TEXT:
        logger.error("❌ SOURCE_TEXT vide ! Ajoute la variable d'environnement.")
        return

    # Traduction
    translated_text = translate_text(SOURCE_TEXT)
    
    # Publication
    post_to_channels(translated_text)

if __name__ == "__main__":
    logger.info("🤖 Bot Telegram -> Public démarré")
    main()
