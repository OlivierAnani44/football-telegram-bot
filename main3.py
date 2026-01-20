import os
import requests
from bs4 import BeautifulSoup
import datetime
import feedparser

# ===============================
# VARIABLES ENVIRONNEMENT (Railway)
# ===============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError("⚠️ BOT_TOKEN ou CHANNEL_ID non définis dans les variables d'environnement.")

# ===============================
# CONFIGURATION
# ===============================
rss_feed_url_list = [
    "https://fbref.com/en/comps/12/La-Liga-Stats"  # Exemple de flux RSS FBref
]
max_entries = 5  # nombre d'articles à poster

# ===============================
# FONCTION : GENERER RSS LOCAL
# ===============================
def generate_rss_fbref(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0)"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print("Erreur téléchargement FBref:", r.status_code)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.string if soup.title else "La Liga Stats FBref"
    snippet = f"Statistiques extraites le {datetime.datetime.utcnow().isoformat()}"

    pubdate = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    rss_item = f"""
    <item>
      <title>{title}</title>
      <link>{url}</link>
      <description><![CDATA[{snippet}]]></description>
      <pubDate>{pubdate}</pubDate>
    </item>
    """

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>FBref La Liga Stats</title>
        <link>{url}</link>
        <description>Flux RSS généré automatiquement pour les stats La Liga</description>
        <lastBuildDate>{pubdate}</lastBuildDate>
        {rss_item}
      </channel>
    </rss>
    """

    return rss_feed

# ===============================
# FONCTION : ENVOYER MESSAGE TELEGRAM
# ===============================
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("Erreur Telegram:", r.text)
    else:
        print("Message envoyé avec succès.")

# ===============================
# FONCTION : LIRE RSS ET POSTER
# ===============================
def read_rss_and_post(rss_feed):
    feed = feedparser.parse(rss_feed)
    entries = feed.entries[:max_entries]
    for entry in entries:
        msg = f"<b>{entry.title}</b>\n{entry.description}\n{entry.link}"
        send_to_telegram(msg)

# ===============================
# PROGRAMME PRINCIPAL
# ===============================
def main():
    for rss_url in rss_feed_url_list:
        print(f"Traitement du flux : {rss_url}")
        rss_feed = generate_rss_fbref(rss_url)
        if rss_feed:
            read_rss_and_post(rss_feed)
        else:
            print("Impossible de générer le RSS pour", rss_url)

if __name__ == "__main__":
    main()
