import os
import feedparser
import asyncio
import aiohttp
import json
import logging
import re
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import argostranslate.translate as argos

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
RSS_URL = "https://feeds.bbci.co.uk/sport/football/rss.xml"

POSTED_FILE = "posted.json"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BBC-FR")

bot = Bot(BOT_TOKEN)

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(data), f)

posted = load_posted()

def translate(text):
    return argos.translate(text, "en", "fr")

async def fetch_article(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=20) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    if not article:
        return ""

    text = article.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)

async def main():
    log.info("🤖 Bot BBC Football FR démarré")
    feed = feedparser.parse(RSS_URL)

    for entry in feed.entries:
        if entry.link in posted:
            continue

        article = await fetch_article(entry.link)
        if not article:
            log.warning("⚠️ Article vide, skip")
            continue

        title_fr = translate(entry.title)
        body_fr = translate(article[:2000])

        message = f"""
⚽ <b>{title_fr}</b>

<blockquote>{body_fr[:900]}...</blockquote>

📰 <b>Source :</b> BBC Sport
🕐 <b>Publié :</b> {datetime.now().strftime('%H:%M')}

#Football #CAN #BBC
""".strip()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Lire l'article", url=entry.link)]
        ])

        for ch in CHANNELS:
            await bot.send_message(
                chat_id=ch,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        posted.add(entry.link)
        save_posted(posted)
        await asyncio.sleep(600)

asyncio.run(main())
