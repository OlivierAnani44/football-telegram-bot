import os
import asyncio
import httpx
import json
import logging
from datetime import datetime

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

SCOREBAT_API = "https://www.scorebat.com/video-api/v3/"
POSTED_FILE = "posted.json"

CHECK_INTERVAL = 300  # 5 minutes

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ScoreBatBot")

# ================= UTILS =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(data), f)

# ================= TELEGRAM =================
async def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": False
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        if r.status_code != 200:
            logger.error(f"Telegram error {r.status_code}: {r.text}")

# ================= SCOREBAT =================
async def fetch_matches():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(SCOREBAT_API)
        r.raise_for_status()
        return r.json()["response"]

# ================= MAIN LOGIC =================
async def process_matches():
    posted = load_posted()
    matches = await fetch_matches()

    for match in matches:
        match_id = match.get("title")
        if not match_id or match_id in posted:
            continue

        competition = match.get("competition", {}).get("name", "Unknown league")
        title = match.get("title", "Match")
        date = match.get("date", "")
        url = match.get("matchviewUrl", "")
        videos = match.get("videos", [])

        message = f"⚽ {title}\n"
        message += f"🏆 {competition}\n"
        message += f"🕒 {date}\n\n"

        if videos:
            message += "🎥 Highlights & Goals:\n"
            for v in videos[:3]:
                message += f"▶️ {v.get('title')}\n{v.get('embed')}\n\n"
        else:
            message += "❌ No video available\n"

        message += f"🔗 {url}"

        await send_message(message)
        posted.add(match_id)
        save_posted(posted)

        logger.info(f"Posted: {title}")
        await asyncio.sleep(3)

# ================= LOOP =================
async def main():
    await send_message("🚀 ScoreBat Football Bot started")
    while True:
        try:
            await process_matches()
        except Exception as e:
            logger.error(f"Error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
