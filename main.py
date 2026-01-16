import os
import feedparser
import json
import asyncio
import logging
import re
import requests
from telegram import Bot
from bs4 import BeautifulSoup

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.ai/rewrite"  # URL de l'API Groq, à adapter selon la documentation

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

# 🚀 Réécriture de l'article avec l'API Groq (FRANÇAIS et accrocheur)
async def rewrite_article(text):
    # Supprimer les liens
    text_no_links = re.sub(r'http\S+', '', text)

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "input_text": text_no_links,
        "language": "fr",  # Demander la réécriture en français
        "tone": "dynamic",  # Indique que tu veux un ton dynamique
        "use_emojis": True,  # Demander l'utilisation d'emojis
    }

    try:
        # Effectuer la requête POST à l'API de Groq
        response = requests.post(GROQ_API_URL, headers=headers, json=data)
        
        if response.status_code == 200:
            rewritten = response.json().get("rewritten_text", "").strip()
            return rewritten
        else:
            logging.error(f"Erreur API Groq : {response.status_code} - {response.text}")
            return text_no_links[:300] + "..."  # Retourne un texte tronqué en cas d'erreur
    except Exception as e:
        logging.error(f"Erreur lors de l'appel à l'API Groq : {e}")
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
