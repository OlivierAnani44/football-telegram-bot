import os
import re
import json
import random
import feedparser
import logging
import aiohttp
import asyncio
from telegram import Bot
from deep_translator import GoogleTranslator

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [ch.strip() for ch in os.getenv("CHANNELS", "").split(",") if ch.strip()]
RSS_FEED = "https://www.allocine.fr/rss/news.xml"  # RSS Allociné
TEMP_IMAGE_FILE = "/tmp/image.jpg"
POSTED_FILE = "posted.json"
POST_INTERVAL = 30 * 60  # 30 minutes

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)

# ---------------- VARIANTES ----------------
TITLE_VARIANTS = [
    "CINÉ INFO", "ACTU FILMS", "NEWS SÉRIES", "FLASH CINÉ",
    "DERNIÈRE MINUTE CINÉ", "ACTUALITÉ FILM", "SÉRIES À LA UNE",
    "LE POINT CINÉ", "INFO FILM", "RÉSUMÉ SÉRIES"
]

HASHTAG_VARIANTS = [
    "#Cinéma", "#Films", "#Séries", "#ActuCiné", "#SortiesCiné",
    "#FilmFrançais", "#SeriesFrançaises", "#ActualitéCinéma",
    "#FansDeCinéma", "#CinéNews", "#CultureCiné", "#Streaming",
    "#BoxOffice", "#FilmDuJour", "#SerieDuJour"
]

COMMENT_VARIANTS = [
    "💬 Qu’en pensez-vous ?", "🗣️ Partagez votre avis en commentaire",
    "👇 Votre réaction nous intéresse", "🎬 Dites-nous ce que vous en pensez",
    "🔥 Vous êtes fan de cette sortie ?", "📢 Débattons-en !",
    "🤔 Bonne ou mauvaise nouvelle selon vous ?", "💭 Votre analyse ici",
    "📝 Partagez votre opinion", "🙌 On attend vos réactions",
    "👀 Votre point de vue compte", "🎞️ Fans de cinéma, à vous la parole"
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
def format_message(title, summary):
    header = random.choice(TITLE_VARIANTS)
    hashtags = " ".join(random.sample(HASHTAG_VARIANTS, 5))
    comment = random.choice(COMMENT_VARIANTS)
    return f"""
🎬🎥 <b>{header} :</b> <i>{title}</i>

<blockquote>{summary}</blockquote>

{hashtags}

<b>{comment}</b>
""".strip()

# ---------------- TRI INTELLIGENT ----------------
def compute_importance(entry):
    summary = re.sub("<.*?>", "", entry.get("summary", "")).lower()
    title = entry.get("title", "").lower()

    keywords_priority = {
        "première": 10,
        "sortie": 10,
        "box-office": 8,
        "critique": 8,
        "série": 7,
        "film": 7,
        "festival": 12,
        "oscar": 15,
        "cannes": 15,
        "acteur": 6,
        "réalisateur": 6,
        "cinéma": 5
    }

    score = len(summary.split())
    for kw, val in keywords_priority.items():
        if kw in summary or kw in title:
            score += val

    return score

def select_most_important(entries, posted):
    candidates = [e for e in entries if (e.get("id") or e.get("link") or e.get("title")) not in posted]
    if not candidates:
        return None
    candidates.sort(key=compute_importance, reverse=True)
    return candidates[0]

# ---------------- POST ----------------
async def post_entry(entry, posted):
    title = await translate(entry.get("title", ""))
    summary = await translate(re.sub("<.*?>", "", entry.get("summary", "")))
    entry_id = entry.get("id") or entry.get("link") or title

    if entry_id in posted:
        return False

    image_url = extract_image(entry)
    image_path = await download_image(image_url)
    message = format_message(title, summary)

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
    logger.info("🤖 Bot Allociné lancé, un post toutes les 30 minutes")

    while True:
        feed = feedparser.parse(RSS_FEED)
        entries = feed.entries[:30]

        post_to_send = select_most_important(entries, posted)
        if post_to_send:
            await post_entry(post_to_send, posted)
        else:
            logger.info("⚠️ Aucun nouvel article à publier")

        logger.info(f"⏳ Attente de {POST_INTERVAL//60} minutes avant le prochain post")
        await asyncio.sleep(POST_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main_loop())
