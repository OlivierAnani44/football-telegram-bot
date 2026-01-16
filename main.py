import os
import feedparser
import json
import asyncio
import logging
import re
import openai
from telegram import Bot

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

POSTED_FILE = "posted.json"
DEFAULT_IMAGE = "https://i.imgur.com/7vQKX0l.png"

# ⚙️ Initialisation bot et logging
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(filename="bot.log", level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 🔄 Chargement des liens déjà postés
def load_posted_links():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted_links():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted_links), f, ensure_ascii=False, indent=2)

posted_links = load_posted_links()

# 🖼️ Récupération de l'image depuis le flux RSS
def get_image(entry):
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get('url')
    if "links" in entry:
        for link in entry.links:
            if "image" in link.type:
                return link.href
    return DEFAULT_IMAGE

# 🔤 Échappement MarkdownV2
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"""
    return ''.join(['\\' + c if c in escape_chars else c for c in text])

# 🚀 Réécriture de l'article avec IA pour Telegram (français et accrocheur)
async def rewrite_article(text):
    # Supprimer les liens
    text_no_links = re.sub(r'http\S+', '', text)
    prompt = (
        f"Réécris ce texte en français pour Telegram de manière dynamique et accrocheuse. "
        f"Utilise des phrases courtes, des emoj
