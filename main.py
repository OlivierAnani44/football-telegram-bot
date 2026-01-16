import os
import feedparser
import requests
import time
import schedule
from telegram import Bot

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml"
]

bot = Bot(token=BOT_TOKEN)
posted_links = set()

def get_image(entry):
    if "media_content" in entry:
        return entry.media_content[0]['url']
    if "links" in entry:
        for link in entry.links:
            if "image" in link.type:
                return link.href
    return None

def post_news():
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:3]:
            if entry.link in posted_links:
                continue

            title = entry.title
            link = entry.link
            summary = entry.summary[:300] + "..."

            image_url = get_image(entry)

            message = f"""
⚽ **ACTUALITÉ FOOTBALL**

🔥 {title}

📰 {summary}

🔗 Lire l'article : {link}
"""

            try:
                if image_url:
                    bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=image_url,
                        caption=message,
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message,
                        parse_mode="Markdown"
                    )

                posted_links.add(link)
                time.sleep(5)

            except Exception as e:
                print("Erreur :", e)

def start_bot():
    post_news()

schedule.every(30).minutes.do(start_bot)

print("🤖 Bot football lancé...")

while True:
    schedule.run_pending()
    time.sleep(1)
