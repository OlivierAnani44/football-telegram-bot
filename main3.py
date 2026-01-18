import os
import asyncio
import aiohttp
import json
import logging
from datetime import date
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]
SPORTDB_API_KEY = os.getenv("SPORTDB_API_KEY", "1")

API_BASE = f"https://www.thesportsdb.com/api/v1/json/{SPORTDB_API_KEY}"

FILES = {
    "startup": "startup.json",
    "today": "today.json",
    "events": "events.json"
}

DEFAULT_IMAGE = "https://i.imgur.com/8QfYJZK.jpg"

# ================= INIT =================
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

# ================= SEND =================
async def send(text):
    for ch in CHANNELS:
        await bot.send_photo(
            chat_id=ch,
            photo=DEFAULT_IMAGE,
            caption=text,
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)

# ================= API =================
async def api_get(session, endpoint):
    url = f"{API_BASE}/{endpoint}"
    async with session.get(url) as r:
        if r.status != 200:
            raise Exception(f"API ERROR {r.status}")
        return await r.json()

# ================= STARTUP =================
async def startup():
    if not os.path.exists(FILES["startup"]):
        await send(
            "👋 *Bot Football ACTIF*\n\n"
            "⚽ Matchs du jour\n"
            "🔴 Live scores\n"
            "⏸ Mi-temps\n"
            "🏁 Scores finaux\n\n"
            "🔥 Bon match à tous !"
        )
        save(FILES["startup"], {"ok": True})

# ================= MATCHS DU JOUR =================
async def post_today(session):
    today = date.today().strftime("%Y-%m-%d")
    state = load(FILES["today"], {})

    if state.get("date") == today:
        return

    data = await api_get(session, f"eventsday.php?d={today}&s=Soccer")
    events = data.get("events")

    if not events:
        return

    lines = []
    for e in events[:20]:
        lines.append(f"⚔️ {e['strHomeTeam']} vs {e['strAwayTeam']}")

    await send(
        f"📅 *MATCHS DU JOUR ({today})*\n\n" + "\n".join(lines)
    )

    save(FILES["today"], {"date": today})

# ================= LIVE + EVENTS =================
async def live_events(session):
    data = await api_get(session, "livescore.php?s=Soccer")
    events = data.get("events")

    if not events:
        return

    live_lines = []

    for e in events:
        event_id = e["idEvent"]
        home = e["strHomeTeam"]
        away = e["strAwayTeam"]
        sh = e["intHomeScore"]
        sa = e["intAwayScore"]
        status = e.get("strStatus", "LIVE")

        # LIVE MESSAGE
        live_lines.append(f"🔴 {home} {sh}–{sa} {away}")

        # MI-TEMPS
        if status == "HT":
            key = f"{event_id}-HT"
            if key not in events_posted:
                await send(
                    f"⏸ *MI-TEMPS*\n\n"
                    f"{home} {sh}–{sa} {away}"
                )
                events_posted.add(key)

        # FIN DE MATCH
        if status == "FT":
            key = f"{event_id}-FT"
            if key not in events_posted:
                await send(
                    f"🏁 *FIN DU MATCH*\n\n"
                    f"{home} {sh}–{sa} {away}"
                )
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
