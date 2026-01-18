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
VIDEOS_LIMIT = 3      # nombre max de vidéos par match
EMBED_MAX_LENGTH = 800  # tronquer l'embed si trop long

# ================= LOG =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

def format_date(date_str):
    if not date_str:
        return "Unknown date"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M UTC")
    except Exception:
        return date_str

# ================= TELEGRAM =================
async def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": False
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            logger.info("Message sent successfully")
    except httpx.HTTPStatusError as e:
        logger.error(f"Telegram error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

# ================= SCOREBAT =================
async def process_matches():
    posted = load_posted()
    matches = await fetch_matches()

    # Filtrer uniquement les dicts
    valid_matches = [m for m in matches if isinstance(m, dict)]
    invalid_count = len(matches) - len(valid_matches)
    if invalid_count > 0:
        logger.warning(f"Ignored {invalid_count} invalid matches (not dict)")

    new_posts = 0
    for match in valid_matches:
        match_id = match.get("title")
        if not match_id or match_id in posted:
            continue

        competition = match.get("competition", {}).get("name", "Unknown league")
        title = match.get("title", "Match")
        date = format_date(match.get("date"))
        url = match.get("matchviewUrl", "")
        videos = match.get("videos", [])

        message = f"⚽ {title}\n"
        message += f"🏆 {competition}\n"
        message += f"🕒 {date}\n\n"

        if videos:
            message += "🎥 Highlights & Goals:\n"
            for v in videos[:VIDEOS_LIMIT]:
                embed = v.get("embed", "")
                if len(embed) > EMBED_MAX_LENGTH:
                    embed = embed[:EMBED_MAX_LENGTH] + "..."
                message += f"▶️ {v.get('title')}\n{embed}\n\n"
        else:
            message += "❌ No video available\n"

        message += f"🔗 {url}"

        await send_message(message)
        posted.add(match_id)
        new_posts += 1

        await asyncio.sleep(3)  # éviter de spammer Telegram

    if new_posts > 0:
        save_posted(posted)
        logger.info(f"Posted {new_posts} new matches")
    else:
        logger.info("No new matches to post")


# ================= LOOP =================
async def main():
    await send_message("🚀 ScoreBat Football Bot started")
    while True:
        try:
            await process_matches()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
