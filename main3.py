import os
import json
import asyncio
import aiohttp
import logging
from datetime import datetime, date
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
SPORTDB_API_KEY = os.getenv("SPORTDB_API_KEY")

API_BASE = "https://sportdb.dev/api/football"

FILES = {
    "startup": "startup.json",
    "today": "today.json",
    "events": "events.json",
    "hour": "hour.json"
}

DEFAULT_IMAGE = "https://i.imgur.com/8QfYJZK.jpg"

bot = Bot(BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ================= UTILS =================
def load(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f)

events_posted = set(load(FILES["events"], []))

# ================= TELEGRAM =================
async def send(text):
    for ch in CHANNELS:
        await bot.send_photo(
            chat_id=ch,
            photo=DEFAULT_IMAGE,
            caption=text,
            parse_mode="Markdown"
        )
        await asyncio.sleep(1.5)

# ================= STARTUP =================
async def startup():
    if not os.path.exists(FILES["startup"]):
        await send(
            "👋 *Bot Football activé*\n\n"
            "⚽ Scores en direct\n"
            "📅 Matchs du jour\n"
            "⏸ Mi-temps\n\n"
            "🔥 Bon match à tous !"
        )
        save(FILES["startup"], {"ok": True})

# ================= API =================
async def api_get(session, endpoint):
    headers = {"Authorization": f"Bearer {SPORTDB_API_KEY}"}
    async with session.get(f"{API_BASE}/{endpoint}", headers=headers) as r:
        return await r.json()

# ================= MATCHS DU JOUR =================
async def post_today(session):
    state = load(FILES["today"], {})
    today = str(date.today())

    if state.get("date") == today:
        return

    data = await api_get(session, "fixtures")
    matches = [
        m for m in data.get("data", [])
        if m.get("date", "").startswith(today)
    ]

    if not matches:
        return

    lines = [
        f"⚔️ {m['home_team']['name']} vs {m['away_team']['name']}"
        for m in matches[:20]
    ]

    await send(
        f"📅 *MATCHS DU JOUR ({date.today().strftime('%d/%m')})*\n\n"
        + "\n".join(lines)
    )

    save(FILES["today"], {"date": today})

# ================= LIVE =================
async def post_live(session):
    hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
    state = load(FILES["hour"], {})

    if state.get("hour") == hour:
        return

    data = await api_get(session, "live")
    matches = data.get("data", [])

    if not matches:
        return

    lines = [
        f"🔴 {m['home_team']['name']} {m['score']['home']}–{m['score']['away']} "
        f"{m['away_team']['name']} ({m['minute']}′)"
        for m in matches[:15]
    ]

    await send("🔴 *MATCHS EN COURS*\n\n" + "\n".join(lines))
    save(FILES["hour"], {"hour": hour})

# ================= MI-TEMPS =================
async def halftime(session):
    data = await api_get(session, "live")
    matches = data.get("data", [])

    for m in matches:
        if m.get("status") == "HT":
            key = f"{m['id']}-HT"
            if key in events_posted:
                continue

            await send(
                f"⏸ *MI-TEMPS*\n\n"
                f"{m['home_team']['name']} {m['score']['home']}–{m['score']['away']} "
                f"{m['away_team']['name']}\n"
                f"🏆 {m['league']['name']}"
            )

            events_posted.add(key)

    save(FILES["events"], list(events_posted))

# ================= MAIN LOOP =================
async def main():
    await startup()

    async with aiohttp.ClientSession() as session:
        while True:
            await post_today(session)
            await post_live(session)
            await halftime(session)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
