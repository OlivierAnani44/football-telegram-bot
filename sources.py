import feedparser

RSS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.goal.com/fr/feeds/news"
]

def fetch_news():
    articles = []

    for url in RSS:
        feed = feedparser.parse(url)
        for e in feed.entries[:3]:
            articles.append({
                "title": e.title,
                "summary": e.summary,
                "link": e.link,
                "image": e.media_content[0]['url'] if "media_content" in e else None
            })

    return articles
