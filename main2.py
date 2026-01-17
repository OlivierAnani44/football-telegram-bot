import os
import feedparser
import json
import asyncio
import logging
import re
import random
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError
from bs4 import BeautifulSoup
import aiohttp

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

RSS_FEEDS = [
    "https://www.allocine.fr/rss/news.xml",
    "https://www.seriesaddict.fr/rss/news.xml"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500
MIN_POST_INTERVAL = 300  # ⏱️ 5 minutes minimum entre chaque post

bot = Bot(token=BOT_TOKEN)

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- DATA ----------------
EMOJI_CATEGORIES = {
    "sortie": ["🎬", "🍿", "🎥"],
    "critique": ["⭐", "📝"],
    "bande_annonce": ["▶️", "🎞️"],
    "casting": ["🎭"],
    "general": ["📰", "🔥"]
}

PHRASES_ACCROCHE = {
    "general": ["📰 INFO : ", "⚡ ACTU : ", "🔥 NOUVEAUTÉ : "]
}

HASHTAGS_FR = ["#Film", "#Série", "#Cinéma", "#Actu", "#PopCulture"]

ENGAGEMENT_PHRASES = [
    "💬 *Votre avis nous intéresse !*\n👇 Dites-nous ce que vous en pensez",
    "🗣️ *Débat ouvert !*\n👇 Réagissez en commentaire",
    "🍿 *Alors, verdict ?*\n👇 On en parle juste en dessous",
    "🔥 *Ça fait réagir ?*\n👇 Laissez votre avis"
]

CATEGORY_QUESTIONS = {
    "sortie": ["🎬 Vous attendez cette sortie ?", "🍿 Hâte ou pas ?"],
    "critique": ["⭐ Vous êtes d’accord avec cette critique ?", "📝 Quelle note lui donneriez-vous ?"],
    "bande_annonce": ["▶️ Cette bande-annonce vous convainc ?", "🎞️ Ça donne envie ?"],
    "casting": ["🎭 Bon choix de casting selon vous ?", "🤔 Casting réussi ?"],
    "general": ["📰 Qu’en pensez-vous ?", "🤔 Votre avis ?"]
}

# ---------------- STORAGE ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links)[-MAX_POSTED_LINKS:], f, ensure_ascii=False, indent=2)

posted_links = load_posted()
last_post_time = 0

# ---------------- UTILS ----------------
def escape_md(text):
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def clean_text(text, max_len=500):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")

def analyze(title, summary):
    t = f"{title} {summary}".lower()
    if "bande" in t or "trailer" in t:
        return "bande_annonce"
    if "critique" in t or "avis" in t:
        return "critique"
    if "casting" in t or "acteur" in t:
        return "casting"
    if "sortie" in t or "film" in t or "série" in t:
        return "sortie"
    return "general"

def extract_image(entry):
    if "media_content" in entry:
        return entry.media_content[0].get("url")
    soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
    img = soup.find("img")
    return img["src"] if img else None

# ---------------- MESSAGE ----------------
def generate_message(title, summary, source):
    cat = analyze(title, summary)

    msg = (
        f"{random.choice(EMOJI_CATEGORIES[cat])} "
        f"{random.choice(PHRASES_ACCROCHE['general'])}"
        f"*{clean_text(title, 80)}*\n\n"
        f"{clean_text(summary)}\n\n"
        f"📰 *Source :* {source}\n"
        f"🕐 *Publié :* {datetime.now().strftime('%H:%M')}\n"
        f"📊 *Catégorie :* {cat.upper()}\n\n"
        f"❓ *{random.choice(CATEGORY_QUESTIONS[cat])}*\n"
        f"{random.choice(ENGAGEMENT_PHRASES)}\n\n"
        f"{' '.join(HASHTAGS_FR)}"
    )
    return escape_md(msg)

# ---------------- POST ----------------
async def post(photo, text):
    for channel in CHANNELS:
        try:
            if photo:
                await bot.send_photo(channel, photo=photo, caption=text, parse_mode="MarkdownV2")
            else:
                await bot.send_message(channel, text=text, parse_mode="MarkdownV2")
            logger.info(f"✅ Posté sur {channel}")
        except TelegramError as e:
            logger.error(e)

# ---------------- SCHEDULER ----------------
async def scheduler():
    global last_post_time

    async with aiohttp.ClientSession() as session:
        while True:
            for feed_url in RSS_FEEDS:
                async with session.get(feed_url) as r:
                    feed = feedparser.parse(await r.text())

                for entry in feed.entries:
                    if time.time() - last_post_time < MIN_POST_INTERVAL:
                        continue

                    link = entry.get("link")
                    if not link or link in posted_links:
                        continue

                    msg = generate_message(
                        entry.get("title", ""),
                        entry.get("summary", ""),
                        feed.feed.get("title", "Média")
                    )

                    await post(extract_image(entry), msg)

                    posted_links.add(link)
                    save_posted()
                    last_post_time = time.time()

                    break  # ⛔ UN SEUL POST MAX

            await asyncio.sleep(60)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    import time
    logger.info("🤖 Bot démarré")
    asyncio.run(scheduler())
