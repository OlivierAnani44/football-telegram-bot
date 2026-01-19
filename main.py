import os
import re
import json
import random
import feedparser
import logging
import aiohttp
import asyncio
from datetime import datetime
from telegram import Bot
from deep_translator import GoogleTranslator

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [ch.strip() for ch in os.getenv("CHANNELS", "").split(",") if ch.strip()]
RSS_FEED = "https://feeds.bbci.co.uk/sport/football/rss.xml"
TEMP_IMAGE_FILE = "/tmp/image.jpg"
POSTED_FILE = "posted.json"
POST_INTERVAL = 30 * 60  # 30 minutes en secondes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)

# ---------------- VARIANTES ----------------
TITLE_VARIANTS = [
    "NOUVELLE FOOT", "INFO FOOT", "ACTUALITÉ FOOT", "FLASH FOOT",
    "DERNIÈRE MINUTE FOOT", "ACTU FOOTBALL", "FOOT À LA UNE",
    "LE POINT FOOT", "INFO MATCH", "RÉSUMÉ FOOT", "FOOT AUJOURD’HUI",
    "ACTU MATCH", "FOOT AFRICAIN", "AFCON ACTUALITÉ", "FOOT INTERNATIONAL",
    "LE FAIT DU JOUR FOOT", "ACTUALITÉ SPORT FOOT", "FLASH MATCH",
    "FOOT EN DIRECT", "FOOT : L’ESSENTIEL"
]

HASHTAG_VARIANTS = [
    "#Football", "#Foot", "#ActuFoot", "#InfoFoot", "#FootActu",
    "#FootballAfricain", "#Afcon", "#FootInternational",
    "#MatchDeFoot", "#FootAujourdHui", "#PassionFoot",
    "#FansDeFoot", "#ActualiteSportive", "#FootNews",
    "#FootAfrique", "#FootDuJour", "#ResumeFoot",
    "#MondeDuFoot", "#FootLive", "#CultureFoot"
]

COMMENT_VARIANTS = [
    "💬 Qu’en pensez-vous ?", "🗣️ Donnez votre avis en commentaire",
    "👇 Votre réaction nous intéresse", "⚽ Dites-nous ce que vous en pensez",
    "🔥 Êtes-vous d’accord avec cette info ?", "📢 Débattons-en dans les commentaires",
    "🤔 Bonne ou mauvaise nouvelle selon vous ?", "💭 Votre analyse en commentaire",
    "📝 Partagez votre opinion", "🙌 On attend vos réactions",
    "👀 Votre point de vue compte", "⚽ Fans de foot, à vous la parole",
    "📣 Laissez votre avis", "🧠 Analysez cette actu avec nous",
    "🔥 Réagissez maintenant", "👇 Dites-le-nous en commentaire",
    "🎯 Quel est votre avis ?", "💬 On lit vos commentaires",
    "⚽ Vous validez ou pas ?", "🗨️ Exprimez-vous !"
]

# ---------------- JSON POSTÉS ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f, ensure_ascii=False, indent=2)

# ---------------- IMAGE ----------------
def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    if "media_thumbnail" in entry:
        return entry.media_thumbnail[0].get("url")
    html = entry.get("summary", "")
    match = re.search(r'<img[^>]+src="([^">]+)"', html)
    return match.group(1) if match else None

async def download_image(url):
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(TEMP_IMAGE_FILE, "wb") as f:
                        f.write(await resp.read())
                    return TEMP_IMAGE_FILE
    except Exception as e:
        logger.error(f"❌ Image error : {e}")
    return None

# ---------------- TRANSLATION ----------------
async def translate(text):
    try:
        return GoogleTranslator(source="auto", target="fr").translate(text)
    except Exception:
        return text

# ---------------- FORMAT MESSAGE ----------------
def format_message(title, summary, published):
    header = random.choice(TITLE_VARIANTS)
    hashtags = " ".join(random.sample(HASHTAG_VARIANTS, 5))
    comment = random.choice(COMMENT_VARIANTS)

    return f"""
🔥🔥 <b>{header} :</b> <i>{title}</i>

<blockquote>{summary}</blockquote>

📌 <b>Source :</b> BBC Sport
⏰ <b>Publié :</b> {published}
🏷️ <b>Catégorie :</b> MATCH

{hashtags}

<b>{comment}</b>
""".strip()

# ---------------- TRI DES ARTICLES ----------------
def sort_entries(entries):
    # Critère simple : longueur du résumé + présence de mots clés importants
    keywords = ["goal", "but", "score", "victoire", "défaite", "titre", "championnat"]
    def importance(entry):
        summary = re.sub("<.*?>", "", entry.get("summary", "")).lower()
        score = len(summary.split())
        score += sum(word in summary for word in keywords) * 10
        return score
    return sorted(entries, key=importance, reverse=True)

# ---------------- POST ----------------
async def post_entry(entry, posted):
    title = await translate(entry.get("title", ""))
    summary = await translate(re.sub("<.*?>", "", entry.get("summary", "")))
    published = entry.get("published", "—")

    # Vérifier si déjà posté
    entry_id = entry.get("id") or entry.get("link") or title
    if entry_id in posted:
        return False

    image_url = extract_image(entry)
    image_path = await download_image(image_url)
    message = format_message(title, summary, published)

    for ch in CHANNELS:
        try:
            if image_path:
                with open(image_path, "rb") as img:
                    await bot.send_photo(
                        chat_id=ch,
                        photo=img,
                        caption=message[:1024],
                        parse_mode="HTML"
                    )
            else:
                await bot.send_message(
                    chat_id=ch,
                    text=message,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            logger.info(f"✅ Publié sur {ch} : {title}")
        except Exception as e:
            logger.error(f"❌ Telegram error : {e}")

    posted.add(entry_id)
    save_posted(posted)
    return True

# ---------------- MAIN LOOP ----------------
async def main_loop():
    posted = load_posted()
    logger.info("🤖 Bot lancé et en attente de posts toutes les 30 minutes")

    while True:
        feed = feedparser.parse(RSS_FEED)
        entries = feed.entries[:20]  # On prend max 20 pour éviter surcharge
        entries = sort_entries(entries)

        for entry in entries:
            await post_entry(entry, posted)
            await asyncio.sleep(5)

        logger.info(f"⏳ Attente de {POST_INTERVAL//60} minutes avant le prochain post")
        await asyncio.sleep(POST_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main_loop())
