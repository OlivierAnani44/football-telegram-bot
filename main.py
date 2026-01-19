import os
import asyncio
import logging
from telegram import Bot
from deep_translator import LibreTranslator, GoogleTranslator

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [
    "@footinfo_vf_fr",
    "@mrxpronos_actu"
]

SOURCE_FILE = "message.txt"

# ================== LOGGING ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

# ================== UTILS ==================
def clean_text(text: str) -> str:
    return " ".join(text.strip().split())

def translate_safe(text: str) -> str:
    text = clean_text(text)

    if not text:
        return text

    text = text[:4000]

    # 1️⃣ LibreTranslate serveur 1
    try:
        return LibreTranslator(
            source="en",
            target="fr",
            base_url="https://libretranslate.de"
        ).translate(text)
    except Exception:
        pass

    # 2️⃣ LibreTranslate serveur 2
    try:
        return LibreTranslator(
            source="en",
            target="fr",
            base_url="https://libretranslate.com"
        ).translate(text)
    except Exception:
        pass

    # 3️⃣ Google fallback
    try:
        return GoogleTranslator(
            source="en",
            target="fr"
        ).translate(text)
    except Exception:
        pass

    logger.error("❌ Traduction impossible")
    return f"⚠️ Traduction temporairement indisponible\n\n{text}"

# ================== MAIN ==================
async def main():
    logger.info("🤖 Bot Telegram démarré")

    if not os.path.exists(SOURCE_FILE):
        logger.error("❌ message.txt introuvable")
        return

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        original_text = f.read()

    translated = translate_safe(original_text)

    final_message = f"📰 <b>ACTUALITÉ FOOT</b>\n\n{translated}"

    for ch in CHANNELS:
        try:
            await bot.send_message(
                chat_id=ch,
                text=final_message,
                parse_mode="HTML"
            )
            logger.info(f"✅ Publié sur {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur envoi {ch} : {e}")

# ================== RUN ==================
if __name__ == "__main__":
    asyncio.run(main())
