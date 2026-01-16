import asyncio
import aiohttp
import os
from bs4 import BeautifulSoup
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHECK_INTERVAL = 900  # 15 minutes
SOURCE_URL = "https://www.footmercato.net/actualite-a-la-une"
POSTED_FILE = "posted.txt"
# ==========================================

bot = Bot(token=BOT_TOKEN)

# ---------- Gestion des articles déjà publiés ----------
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_posted(url):
    with open(POSTED_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

# ---------- Récupération des articles ----------
async def get_articles():
    async with aiohttp.ClientSession() as session:
        async with session.get(SOURCE_URL, timeout=15) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    articles = []

    for item in soup.select("article"):
        try:
            title = item.select_one("h2").text.strip()
            link = "https://www.footmercato.net" + item.find("a")["href"]
            image = item.find("img")["src"]
            articles.append((title, link, image))
        except Exception:
            continue

    return articles

# ---------- Publication Telegram ----------
async def post_to_telegram(title, link, image):
    caption = f"⚽ *{title}*\n\n👉 [Lire l'article]({link})"
    await bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=image,
        caption=caption,
        parse_mode="Markdown"
    )

# ---------- Boucle principale ----------
async def main():
    posted = load_posted()

    while True:
        print("🔍 Vérification des nouvelles actualités...")
        try:
            articles = await get_articles()

            for title, link, image in articles:
                if link not in posted:
                    await post_to_telegram(title, link, image)
                    save_posted(link)
                    posted.add(link)
                    print("✅ Publié :", title)
                    await asyncio.sleep(5)

        except Exception as e:
            print("❌ Erreur :", e)

        await asyncio.sleep(CHECK_INTERVAL)

# ---------- Lancement ----------
if __name__ == "__main__":
    asyncio.run(main())
