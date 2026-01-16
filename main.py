import os
import feedparser
import json
import asyncio
import logging
import re
import openai
from telegram import Bot
from bs4 import BeautifulSoup

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

# 🖼️ Récupération de l'image principale depuis le flux RSS
def get_image(entry):
    # 1️⃣ media_content
    if "media_content" in entry and entry.media_content:
        return entry.media_content[0].get('url')
    
    # 2️⃣ enclosures
    if "enclosures" in entry:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href")
    
    # 3️⃣ image dans summary ou content HTML
    content = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "")
    soup = BeautifulSoup(content, "html.parser")
    img_tag = soup.find("img")
    if img_tag and img_tag.get("src"):
        return img_tag.get("src")
    
    # 4️⃣ pas d'image
    return None

# 🔤 Échappement MarkdownV2
def escape_markdown(text):
    escape_chars = r"_*[]()~`>#+-=|{}.!"""
    return ''.join(['\\' + c if c in escape_chars else c for c in text])

# 🚀 Réécriture de l'article avec IA (FRANÇAIS et accrocheur)
async def rewrite_article(text):
    # Supprime les liens
    text_no_links = re.sub(r'http\S+', '', text)

    prompt = f"""
Réécris strictement ce texte en FRANÇAIS pour Telegram, de manière dynamique et accrocheuse.
- Utilise des phrases courtes.
- Ajoute des emojis football ⚽🔥📰.
- Ne mets aucun lien.
- Ne répond jamais en anglais.

Texte à réécrire :
{text_no_links}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )
        rewritten = response['choices'][0]['message']['content'].strip()
        return rewritten
    except Exception as e:
        logging.error(f"Erreur IA : {e}")
        return text_no_links[:300] + "..."

# 📰 Vérifie et publie uniquement les nouveaux articles avec image
async def check_and_post_news():
    new_posts = 0
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:
            if entry.link in posted_links:
                continue

            # Cherche l'image principale
            image_url = get_image(entry)
            if not image_url:
                continue  # on ne publie pas sans image

            # Réécriture
            summary = await rewrite_article(entry.summary)
            title = escape_markdown(entry.title)
            summary = escape_markdown(summary)

            message = f"""⚽ *ACTUALITÉ FOOTBALL*\n
🔥 *{title}*\n
📰 {summary}"""

            try:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=message,
                    parse_mode="MarkdownV2"
                )
                posted_links.add(entry.link)
                save_posted_links()
                new_posts += 1
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"Erreur lors de l'envoi du post : {e}")

    if new_posts:
        print(f"✅ {new_posts} nouvel(le)(s) article(s) publié(s).")
    else:
        print("⏱ Aucun nouvel article pour l'instant.")

# 🔁 Boucle de vérification continue
async def scheduler():
    while True:
        await check_and_post_news()
        await asyncio.sleep(60)  # toutes les 1 minute

# 🏁 Lancement
if __name__ == "__main__":
    print("🤖 Bot football avec IA en français et images principales lancé...")
    asyncio.run(scheduler())
