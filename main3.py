import asyncio
from datetime import date
import httpx
import os

# ---------------- CONFIGURATION ----------------
SPORTMONKS_TOKEN = os.getenv("SPORTMONKS_TOKEN")  # Ton token SportMonks v3/v4
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Ton token Telegram
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")      # ID du chat ou canal Telegram

BASE_URL = "https://soccer.sportmonks.com/api/v3/"

# ---------------- FONCTIONS ----------------

async def sportmonks_get(endpoint, params=None):
    if params is None:
        params = {}
    params["api_token"] = SPORTMONKS_TOKEN
    url = f"{BASE_URL}{endpoint}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"})
        r.raise_for_status()

async def send_photo(photo_url, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url, "caption": caption, "parse_mode": "HTML"})
        r.raise_for_status()

async def post_today():
    today_str = date.today().isoformat()
    
    # ---- Fixtures du jour ----
    try:
        data = await sportmonks_get(f"fixtures/date/{today_str}", params={"include": "localTeam,visitorTeam,highlights"})
    except httpx.HTTPStatusError as e:
        await send_message(f"⚠️ Erreur SportMonks fixtures : {e}")
        return

    for fixture in data.get("data", []):
        home = fixture.get("localTeam", {}).get("data", {}).get("name", "Unknown")
        away = fixture.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
        score_home = fixture.get("scores", {}).get("localteam_score", 0)
        score_away = fixture.get("scores", {}).get("visitorteam_score", 0)
        match_text = f"⚽ {home} vs {away} \nScore: {score_home}-{score_away}"

        await send_message(match_text)

        # ---- Highlights vidéo ----
        highlights = fixture.get("highlights", {}).get("data", [])
        for hl in highlights:
            video_url = hl.get("video", "")
            if video_url:
                await send_photo(video_url, caption=f"Highlight: {home} vs {away}")

# ---------------- MAIN ----------------

async def main():
    await send_message("🚀 Bot football démarré (mode v3/v4 SportMonks)")
    await post_today()

if __name__ == "__main__":
    asyncio.run(main())
