import os
import requests

# =============================
# VARIABLES D'ENVIRONNEMENT
# =============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
LEAGUE = "eng.1"  # Exemple : Premier League, changeable

if not BOT_TOKEN or not CHANNEL_ID:
    raise RuntimeError("BOT_TOKEN ou CHANNEL_ID manquant")

# =============================
# FONCTION TELEGRAM
# =============================
def send_to_telegram(msg: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        print("Erreur Telegram:", response.text)
    else:
        print("Message envoyé:", msg[:50], "...")

# =============================
# FONCTION SCORES
# =============================
def get_scores():
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/scoreboard"
    res = requests.get(url).json()
    events = res.get("events", [])
    if not events:
        print("Aucun match trouvé")
        return

    for match in events:
        comp = match["competitions"][0]
        home = comp["competitors"][0]["team"]["shortDisplayName"]
        away = comp["competitors"][1]["team"]["shortDisplayName"]
        score_home = comp["competitors"][0]["score"]
        score_away = comp["competitors"][1]["score"]
        status = comp["status"]["type"]["shortDetail"]
        msg = f"⚽ {home} vs {away}\nScore: {score_home}-{score_away}\nStatut: {status}"
        send_to_telegram(msg)

# =============================
# FONCTION NEWS
# =============================
def get_news():
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/news"
    res = requests.get(url).json()
    articles = res.get("articles", [])
    for article in articles[:5]:  # 5 dernières news
        title = article["headline"]
        link = article["links"]["web"]["href"]
        send_to_telegram(f"📰 {title}\n{link}")

# =============================
# FONCTION STATS MATCH (OPTIONNELLE)
# =============================
def get_match_stats(gameId):
    url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}/summary?event={gameId}"
    res = requests.get(url).json()
    comp = res.get("header", {})
    home = comp.get("competitors", [])[0]["team"]["displayName"]
    away = comp.get("competitors", [])[1]["team"]["displayName"]
    score_home = comp.get("competitors", [])[0]["score"]
    score_away = comp.get("competitors", [])[1]["score"]

    stats = res.get("boxscore", {}).get("teams", [])
    home_stats = stats[0] if len(stats) > 0 else {}
    away_stats = stats[1] if len(stats) > 1 else {}

    shots_home = home_stats.get("statistics", {}).get("shots", "-")
    shots_away = away_stats.get("statistics", {}).get("shots", "-")
    possession_home = home_stats.get("statistics", {}).get("possession", "-")
    possession_away = away_stats.get("statistics", {}).get("possession", "-")

    msg = (
        f"📊 {home} vs {away}\n"
        f"Score: {score_home}-{score_away}\n"
        f"Tirs: {shots_home}-{shots_away} | Possession: {possession_home}-{possession_away}%"
    )
    send_to_telegram(msg)

# =============================
# MAIN
# =============================
def main():
    print("Récupération des scores...")
    get_scores()
    print("Récupération des news...")
    get_news()

    # Exemple de stats match : utiliser un gameId valide
    # gameId = "1234567"
    # get_match_stats(gameId)

if __name__ == "__main__":
    main()
