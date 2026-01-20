import os
import cloudscraper
from bs4 import BeautifulSoup
import datetime
import feedparser

# =====================================
# VARIABLES ENVIRONNEMENT (Railway)
# =====================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =====================================
# CONFIG
# =====================================
RSS_FEED_URL_LIST = ["https://fbref.com/en/comps/12/La-Liga-Stats"]
MAX_ENTRIES = 1

# =====================================
# GENERATE RSS AVEC CLOUDSCRAPER
# =====================================
def generate_rss_from_fbref(url):
    scraper = cloudscraper.create_scraper()
    r = scraper.get(url, timeout=30)
    if r.status_code != 200:
        print("FBref bloqué:", r.status_code)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.text if soup.title else "FBref Football Stats"
    now = datetime.datetime.utcnow()
    pubdate = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    description = (
        f"Statistiques FBref mises à jour<br>"
        f"Compétition : La Liga<br>"
        f"Date UTC : {now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>FBref La Liga RSS</title>
        <link>{url}</link>
        <description>RSS auto généré depuis FBref</description>
        <lastBuildDate>{pubdate}</lastBuildDate>
        <item>
          <title>{title}</title>
          <link>{url}</link>
          <description><![CDATA[{description}]]></description>
          <pubDate>{pubdate}</pubDate>
        </item>
      </channel>
    </rss>
    """

    return rss

# =====================================
# TELEGRAM
# =====================================
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("Erreur Telegram:", r.text)

# =====================================
# PARSE RSS + POST
# =====================================
def parse_and_post(rss_xml):
    feed = feedparser.parse(rss_xml)
    for entry in feed.entries[:MAX_ENTRIES]:
        msg = f"📊 <b>{entry.title}</b>\n\n{entry.description}\n\n🔗 {entry.link}"
        send_to_telegram(msg)

# =====================================
# MAIN
# =====================================
def main():
    for url in RSS_FEED_URL_LIST:
        print("Traitement du flux :", url)
        rss = generate_rss_from_fbref(url)
        if rss:
            parse_and_post(rss)
        else:
            print("RSS non généré")

if __name__ == "__main__":
    main()
