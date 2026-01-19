import asyncio
import httpx
import json
from datetime import date
import os

# ---------------- CONFIG ----------------
SPORTMONKS_TOKEN = os.getenv("SPORTMONKS_TOKEN")  # Ton token SportMonks
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")      # Ton token bot Telegram
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Id du canal ou chat
POSTED_FILE = "posted.json"

BASE_URL = "https://soccer.sportmonks.com/api/v3/"

# ---------------- UTIL ----------------
async def send_message(text: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        )
        resp.raise_for_status()

async def send_photo(photo_url: str, caption: str = ""):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data={"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
        )
        resp.raise_for_status()

async def sportmonks_get(endpoint: str, params=None):
    if params is None:
        params = {}
    params["api_token"] = SPORTMONKS_TOKEN
    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_URL + endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return json.load(f)
    return []

def save_posted(posted):
    with open(POSTED_FILE, "w") as f:
        json.dump(posted, f)

# ---------------- MAIN ----------------
async def post_today():
    posted = load_posted()
    today_str = date.today().isoformat()

    try:
        data = await sportmonks_get(
            "fixtures",
            params={
                "filter[date]": today_str,
                "include": "localTeam,visitorTeam,highlights,scores"
            }
        )

        fixtures = data.get("data", [])
        if not fixtures:
            await send_message(f"⚠️ Aucun match trouvé pour {today_str}")
            return

        for f in fixtures:
            fixture_id = f["id"]
            if fixture_id in posted:
                continue

            home = f.get("localTeam", {}).get("data", {}).get("name", "Unknown")
            away = f.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
            score = f.get("scores", {}).get("localteam_score"), f.get("scores", {}).get("visitorteam_score")
            score_text = f"{score[0] or 0} - {score[1] or 0}"

            # Message texte
            text = f"⚽ {home} vs {away}\nScore: {score_text}"
            await send_message(text)

            # Highlights
            highlights = f.get("highlights", {}).get("data", [])
            for h in highlights:
                video_url = h.get("video_url")
                if video_url:
                    await send_photo(video_url, caption=f"🎥 But : {home} vs {away}")

            posted.append(fixture_id)

        save_posted(posted)

    except httpx.HTTPStatusError as e:
        await send_message(f"⚠️ Erreur SportMonks fixtures : {e}")

# ---------------- RUN ----------------
async def main_loop():
    while True:
        await post_today()
        await asyncio.sleep(60 * 10)  # toutes les 10 minutes

if __name__ == "__main__":
    asyncio.run(main_loop())
