import os
import asyncio
import httpx
from datetime import date
import logging

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Ton token Telegram
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
SPORTMONKS_TOKEN = os.getenv("SPORTMONKS_TOKEN")  # Ton token SportMonks

BASE_URL = "https://soccer.sportmonks.com/api/v3/football/"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ================= TELEGRAM =================
async def send_telegram(text, photo=None):
    for ch in CHANNELS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        if photo:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        async with httpx.AsyncClient() as client:
            try:
                if photo:
                    await client.post(url, data={"chat_id": ch, "caption": text}, files={"photo": photo})
                else:
                    await client.post(url, data={"chat_id": ch, "text": text, "parse_mode": "Markdown"})
            except Exception as e:
                logger.error(f"Telegram send error: {e}")

# ================= SPORTMONKS =================
async def sportmonks_get(endpoint, params=None):
    if params is None:
        params = {}
    params["api_token"] = SPORTMONKS_TOKEN
    async with httpx.AsyncClient() as client:
        r = await client.get(BASE_URL + endpoint, params=params)
        r.raise_for_status()
        return r.json()

# ================= FIXTURES DU JOUR =================
async def post_today():
    today_str = date.today().isoformat()
    data = await sportmonks_get("fixtures", params={
        "date": today_str,
        "include": "localTeam,visitorTeam,highlights"
    })

    if "data" not in data or not data["data"]:
        logger.info("Aucune donnée aujourd'hui")
        return

    messages = []
    for match in data["data"]:
        home = match["localTeam"]["data"]["name"]
        away = match["visitorTeam"]["data"]["name"]
        score_home = match.get("scores", {}).get("localteam_score", "-")
        score_away = match.get("scores", {}).get("visitorteam_score", "-")
        minute = match.get("time", {}).get("minute", "?")

        msg = f"⚽ {home} {score_home}-{score_away} {away} ({minute}')"
        messages.append(msg)

        # Highlights vidéo
        if "highlights" in match and match["highlights"]["data"]:
            for hl in match["highlights"]["data"]:
                video_url = hl.get("video_url")
                if video_url:
                    await send_telegram(f"🎥 Highlight: {home} vs {away}\n{video_url}")

    # Envoyer tous les matchs du jour
    if messages:
        text = f"📅 *Fixtures du jour ({today_str})*\n\n" + "\n".join(messages)
        await send_telegram(text)

# ================= LIVE SCORES =================
async def post_live():
    data = await sportmonks_get("fixtures", params={
        "status": "LIVE",
        "include": "localTeam,visitorTeam,highlights"
    })

    if "data" not in data or not data["data"]:
        logger.info("Aucun match en live")
        return

    for match in data["data"]:
        home = match["localTeam"]["data"]["name"]
        away = match["visitorTeam"]["data"]["name"]
        score_home = match.get("scores", {}).get("localteam_score", "-")
        score_away = match.get("scores", {}).get("visitorteam_score", "-")
        minute = match.get("time", {}).get("minute", "?")
        msg = f"🔴 Live: {home} {score_home}-{score_away} {away} ({minute}')"
        await send_telegram(msg)

# ================= MAIN LOOP =================
async def main_loop():
    while True:
        try:
            await post_today()
            await post_live()
        except Exception as e:
            logger.error(f"Erreur: {e}")
            await send_telegram(f"⚠️ Erreur dans le bot : {e}")
        await asyncio.sleep(60)  # Vérifie toutes les 60 secondes

if __name__ == "__main__":
    asyncio.run(main_loop())
