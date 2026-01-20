import os
import requests
from bs4 import BeautifulSoup
import datetime
import feedparser

# =====================================
# VARIABLES ENVIRONNEMENT (Railway)
# =====================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant dans Railway")

# =====================================
# CONFIG
# =====================================
RSS_FEED_URL_LIST = [
    "https://fbref.com/en/comps/12/La-Liga-Stats"
]
MAX_ENTRIES = 1  # 1 message par exécution (recommandé Railway)

# =====================================
# HEADERS ANTI-403 (CRUCIAL)
# =====================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

# =====================================
# GENERATION RSS DEPUIS FBREF
# =====================================
def generate_rss_from_fbref(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        print("FBref bloqué:", r.status_code)
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.text if soup.title else "FBref Football Stats"
    now = datetime.datetime.utcnow()
    pubdate = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    description = f"""
    Statistiques FBref mises à jour<br>
    Compétition : La Liga<br>
    Date UTC : {now.strftime('%Y-%m-%d %H:%M:%S')}
    """

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
# TELEGRAM SENDER
# =====================================
def send_to_telegram(text):
    endpoint = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    r = requests.post(endpoint, data=payload)
    if r.status_code != 200:
        print("Erreur Telegram:", r.text)

# =====================================
# PARSE RSS + POST
# =====================================
def parse_and_post(rss_xml):
    feed = feedparser.parse(rss_xml)
    for entry in feed.entries[:MAX_ENTRIES]:
        msg = (
            f"📊 <b>{entry.title}</b>\n\n"
            f"{entry.description}\n\n"
            f"🔗 {entry.link}"
        )
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
