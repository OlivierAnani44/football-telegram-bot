import os
import asyncio
import httpx
import json
import logging
from datetime import datetime, date

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
SPORTMONKS_API_TOKEN = os.getenv("SPORTMONKS_API_TOKEN")

POSTED_FILE = "posted.json"
FILES = {
    "today": "today.json",
    "live": "live.json",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ================= UTILS =================
def load(file, default=None):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default or {}

def save(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f)

async def send_message(text):
    async with httpx.AsyncClient() as client:
        for ch in CHANNELS:
            try:
                r = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data={"chat_id": ch, "text": text, "parse_mode": "Markdown"}
                )
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Telegram API error: {e}")

async def send_photo(photo_url, caption):
    async with httpx.AsyncClient() as client:
        for ch in CHANNELS:
            try:
                r = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={"chat_id": ch, "photo": photo_url, "caption": caption, "parse_mode": "Markdown"}
                )
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"Telegram API error: {e}")

async def sportmonks_get(session, endpoint, params=None):
    url = f"https://soccer.sportmonks.com/api/v2.0/{endpoint}"
    params = params or {}
    params["api_token"] = SPORTMONKS_API_TOKEN
    async with session.get(url, params=params) as r:
        data = await r.json()
        return data

# ================= MATCHS DU JOUR =================
async def post_today(session):
    today_str = date.today().isoformat()
    state = load(FILES["today"], {})
    if state.get("date") == today_str:
        return

    data = await sportmonks_get(session, "fixtures", {
        "date": today_str,
        "include": "localTeam,visitorTeam",
        "per_page": 50
    })
    matches = data.get("data") or []

    if not matches:
        logger.info(f"Aucune donnée pour la date {today_str}")
        return

    lines = []
    for m in matches[:20]:
        home = m.get("localTeam", {}).get("data", {}).get("name", "Unknown")
        away = m.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
        time = m.get("time", {}).get("starting_at", {}).get("time", "?")
        lines.append(f"⚔️ {home} vs {away} ({time})")

    await send_message(f"📅 *MATCHS DU JOUR ({today_str})*\n\n" + "\n".join(lines))
    save(FILES["today"], {"date": today_str})

# ================= LIVE SCORES =================
async def post_live(session):
    now_hour = datetime.now().strftime("%Y-%m-%d-%H")
    state = load(FILES["live"], {})
    if state.get("hour") == now_hour:
        return

    data = await sportmonks_get(session, "fixtures", {
        "status": "LIVE",
        "include": "localTeam,visitorTeam",
        "per_page": 50
    })
    matches = data.get("data") or []

    if not matches:
        logger.info(f"Aucun match en live actuellement")
        return

    lines = []
    for m in matches[:15]:
        home = m.get("localTeam", {}).get("data", {}).get("name", "Unknown")
        away = m.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
        score = f"{m.get('scores', {}).get('localteam_score', 0)}–{m.get('scores', {}).get('visitorteam_score', 0)}"
        lines.append(f"🔴 {home} {score} {away}")

    await send_message("🔴 *MATCHS EN COURS*\n\n" + "\n".join(lines))
    save(FILES["live"], {"hour": now_hour})

# ================= MAIN =================
async def main():
    await send_message("🚀 Bot football démarré")
    async with httpx.AsyncClient() as session:
        while True:
            await post_today(session)
            await post_live(session)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
