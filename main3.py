import os
import asyncio
import httpx
import json
from datetime import datetime

# ---------------- CONFIG ----------------
SPORTMONKS_API_TOKEN = os.getenv("SPORTMONKS_API_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_URL = "https://soccer.sportmonks.com/api/v2.0"
POSTED_FILE = "posted.json"  # Pour ne pas poster deux fois

# ---------------- UTIL ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return json.load(f)
    return {"today": [], "live": []}

def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(data, f)

# ---------------- TELEGRAM ----------------
async def send_message(text):
    async with httpx.AsyncClient() as client:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        r = await client.post(url, data=payload)
        r.raise_for_status()

async def send_photo(photo_url, caption=None):
    async with httpx.AsyncClient() as client:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "photo": photo_url}
        if caption:
            payload["caption"] = caption
        r = await client.post(url, data=payload)
        r.raise_for_status()

# ---------------- SPORTMONKS ----------------
async def sportmonks_get(session, endpoint, params=None):
    url = f"{BASE_URL}/{endpoint}"
    params = params or {}
    params["api_token"] = SPORTMONKS_API_TOKEN
    r = await session.get(url, params=params)
    r.raise_for_status()
    return r.json()

# ---------------- MATCHS DU JOUR ----------------
async def post_today(session, posted):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    data = await sportmonks_get(session, f"fixtures/date/{today}", params={"include": "localTeam,visitorTeam,highlights,scores"})
    matches = data.get("data", [])

    for match in matches:
        match_id = str(match["id"])
        if match_id in posted["today"]:
            continue

        home = match.get("localTeam", {}).get("data", {}).get("name", "Unknown")
        away = match.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
        score = f"{match.get('scores', {}).get('localteam_score', 0)} - {match.get('scores', {}).get('visitorteam_score', 0)}"
        status = match.get("time", {}).get("status", "N/A")
        message = f"⚽ <b>{home} vs {away}</b>\nScore : {score}\nStatut : {status}"
        await send_message(message)

        # Vidéos de buts si disponibles
        highlights = match.get("highlights", {}).get("data", [])
        for highlight in highlights:
            video_url = highlight.get("video_url")
            if video_url:
                await send_photo(video_url, caption=f"🎬 But: {home} vs {away}")

        posted["today"].append(match_id)

# ---------------- LIVE SCORES ----------------
async def post_live(session, posted):
    data = await sportmonks_get(session, "livescores", params={"include": "localTeam,visitorTeam,scores"})
    matches = data.get("data", [])

    for match in matches:
        match_id = str(match["id"])
        if match_id in posted["live"]:
            continue

        home = match.get("localTeam", {}).get("data", {}).get("name", "Unknown")
        away = match.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
        score = f"{match.get('scores', {}).get('localteam_score', 0)} - {match.get('scores', {}).get('visitorteam_score', 0)}"
        message = f"🔴 Live: <b>{home} vs {away}</b>\nScore : {score}"
        await send_message(message)

        posted["live"].append(match_id)

# ---------------- MAIN ----------------
async def main_loop():
    posted = load_posted()
    async with httpx.AsyncClient() as session:
        while True:
            try:
                await post_today(session, posted)
                await post_live(session, posted)
                save_posted(posted)
            except Exception as e:
                await send_message(f"⚠️ Erreur dans le bot : {e}")
            await asyncio.sleep(600)  # toutes les 10 minutes

if __name__ == "__main__":
    asyncio.run(main_loop())
