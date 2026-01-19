import os
import json
import asyncio
import aiohttp
import logging
from datetime import date, datetime
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

SPORTMONKS_TOKEN = os.getenv("SPORTMONKS_TOKEN")

BASE_URL = "https://api.sportmonks.com/v3/football"

FILES = {
    "startup": "startup.json",
    "today": "today.json",
    "events": "events.json"
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

async def send(text):
    for ch in CHANNELS:
        await bot.send_photo(
            chat_id=ch,
            photo=DEFAULT_IMAGE,
            caption=text,
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)

# ================= API CALL =================
async def sportmonks_get(session, endpoint, params=None):
    if params is None:
        params = {}
    params["api_token"] = SPORTMONKS_TOKEN
    async with session.get(f"{BASE_URL}/{endpoint}", params=params) as r:
        if r.status != 200:
            txt = await r.text()
            logger.error(f"SportMonks API {r.status}: {txt}")
            return {}
        return await r.json()

# ================= STARTUP =================
async def startup():
    if not os.path.exists(FILES["startup"]):
        await send(
            "👋 *Bot Football ACTIF (SportMonks)*\n\n"
            "⚽ Matchs du jour\n"
            "🔴 Score Live\n"
            "⏱️ Mi‑temps & Scores\n\n"
            "🔥 Bon match à tous !"
        )
        save(FILES["startup"], {"ok": True})

# ================= MATCHS DU JOUR =================
async def post_today(session):
    today_str = date.today().isoformat()
    state = load(FILES["today"], {})
    if state.get("date") == today_str:
        return

    data = await sportmonks_get(session, "fixtures", {"date": today_str})
    matches = data.get("data") or []

    if not matches:
        return

    lines = [
        f"⚔️ {m['home_team']['data']['name']} vs {m['away_team']['data']['name']}"
        for m in matches[:20]
    ]

    await send(
        f"📅 *MATCHS DU JOUR ({today_str})*\n\n" +
        "\n".join(lines)
    )
    save(FILES["today"], {"date": today_str})

# ================= LIVE + EVENTS =================
async def live_events(session):
    data = await sportmonks_get(session, "livescores")
    matches = data.get("data") or []

    if not matches:
        return

    live_lines = []
    for m in matches:
        evt_id = m["id"]
        home = m["home_team"]["data"]["name"]
        away = m["away_team"]["data"]["name"]
        score_h = m["scores"]["localteam_score"]
        score_a = m["scores"]["visitorteam_score"]
        minute = m.get("time", {}).get("status")

        live_lines.append(f"🔴 {home} {score_h}–{score_a} {away} ({minute})")

        # HT → mi‑temps
        if minute == "HT":
            key = f"{evt_id}-HT"
            if key not in events_posted:
                await send(f"⏸ *MI‑TEMPS*\n\n{home} {score_h}–{score_a} {away}")
                events_posted.add(key)

        # FT → fin de match
        if minute == "FT":
            key = f"{evt_id}-FT"
            if key not in events_posted:
                await send(f"🏁 *FIN DU MATCH*\n\n{home} {score_h}–{score_a} {away}")
                events_posted.add(key)

    if live_lines:
        await send("🔴 *MATCHS EN COURS*\n\n" + "\n".join(live_lines[:15]))

    save(FILES["events"], list(events_posted))

# ================= MAIN LOOP =================
async def main():
    await startup()
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await post_today(session)
                await live_events(session)
            except Exception as e:
                logger.error(e)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
