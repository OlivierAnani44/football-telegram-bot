import os
import feedparser
import asyncio
import aiohttp
import json
import logging
import re
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from html import escape

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
RSS_URL = "https://feeds.bbci.co.uk/sport/football/rss.xml"
POSTED_FILE = "posted.json"

LIBRE_TRANSLATE_URL = "https://libretranslate.de/translate"

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BBC-BOT")

bot = Bot(BOT_TOKEN)

# ================= STORAGE =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(data), f)

posted = load_posted()

# ================= TRANSLATION =================
async def translate(text):
    if not text.strip():
        return text

    async with aiohttp.ClientSession() as session:
        payload = {
            "q": text[:4000],  # LIMITE OBLIGATOIRE
            "source": "en",
            "target": "fr",
            "format": "text"
        }
        async with session.post(LIBRE_TRANSLATE_URL, json=payload) as r:
            data = await r.json()
            return data.get("translatedText", text)

# ================= ARTICLE FETCH =================
async def fetch_article(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")

    if not article:
        return ""

    text = article.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text

# ================= MAIN LOOP =================
async def run():
    log.info("🤖 Bot BBC Football FR lancé")
    feed = feedparser.parse(RSS_URL)

    for entry in feed.entries:
        link = entry.link
        if link in posted:
            continue

        log.info(f"📰 Article : {entry.title}")

        article_text = await fetch_article(link)
        translated = await translate(article_text)

        title_fr = await translate(entry.title)
        summary = escape(translated[:1000]) + "..."

        message = f"""
⚽ <b>{escape(title_fr)}</b>

<blockquote>{summary}</blockquote>

📰 <b>Source :</b> BBC Sport
🕐 <b>Publié :</b> {datetime.now().strftime('%H:%M')}

#Football #CAN #BBC
""".strip()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Lire l'article", url=link)]
        ])

        for ch in CHANNELS:
            await bot.send_message(
                chat_id=ch,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        posted.add(link)
        save_posted(posted)

        await asyncio.sleep(600)

asyncio.run(run())
