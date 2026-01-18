import os
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, date
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

DEFAULT_IMAGE = "https://i.imgur.com/8QfYJZK.jpg"

FILES = {
    "startup": "startup.json",
    "today": "today.json",
    "hour": "hour.json",
    "events": "events.json"
}

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

async def send(text):
    for ch in CHANNELS:
        await bot.send_photo(
            chat_id=ch,
            photo=DEFAULT_IMAGE,
            caption=text,
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)

# ================= STARTUP =================
async def startup():
    if not os.path.exists(FILES["startup"]):
        await send(
            "👋 *Salut tout le monde !*\n\n"
            "⚽ Bot Football *ACTIF*\n"
            "• Matchs du jour\n"
            "• Live toutes les 1h\n"
            "• Mi-temps & scores\n\n"
            "🔥 Bon match à tous"
        )
        save(FILES["startup"], {"ok": True})

# ================= FLASHSCORE API =================
# Endpoint général Flashscore JSON
API_URL = "https://d.flashscore.com/x/feed/f_1_0_1_en_1"

async def fetch_json(session, url=API_URL):
    async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as r:
        return await r.json()

def parse_matches_json(data):
    matches = []
    events = data.get("events", [])
    for e in events:
        home = e.get("home", {}).get("name")
        away = e.get("away", {}).get("name")
        sh = str(e.get("homeScore")) if e.get("homeScore") is not None else "-"
        sa = str(e.get("awayScore")) if e.get("awayScore") is not None else "-"
        minute = e.get("status") or "?"
        league = e.get("tournament", {}).get("name") or "Football"

        matches.append({
            "home": home,
            "away": away,
            "sh": sh,
            "sa": sa,
            "minute": minute,
            "league": league
        })
    return matches

# ================= MATCHS DU JOUR =================
async def post_today(session):
    state = load(FILES["today"], {})
    if state.get("date") == str(date.today()):
        return

    data = await fetch_json(session)
    matches = parse_matches_json(data)

    if not matches:
        return

    lines = [f"⚔️ {m['home']} vs {m['away']}" for m in matches[:20]]

    await send(
        f"📅 *MATCHS DU JOUR ({date.today().strftime('%d/%m')})*\n\n" + "\n".join(lines)
    )
    save(FILES["today"], {"date": str(date.today())})

# ================= LIVE HORAIRE =================
async def hourly_live(session):
    hour = datetime.now().strftime("%Y-%m-%d-%H")
    state = load(FILES["hour"], {})

    if state.get("hour") == hour:
        return

    data = await fetch_json(session)
    matches = parse_matches_json(data)

    if not matches:
        return

    lines = [
        f"🔴 {m['home']} {m['sh']}–{m['sa']} {m['away']} ({m['minute']})"
        for m in matches[:15]
    ]

    await send("🔴 *MATCHS EN COURS*\n\n" + "\n".join(lines))
    save(FILES["hour"], {"hour": hour})

# ================= MI-TEMPS =================
async def halftime_events(session):
    data = await fetch_json(session)
    matches = parse_matches_json(data)

    for m in matches:
        if m["minute"] in ["HT", "HT1H", "HT2H"]:
            key = f"{m['home']}-{m['away']}-HT"
            if key in events_posted:
                continue

            await send(
                f"⏸ *MI-TEMPS*\n\n"
                f"{m['home']} {m['sh']}–{m['sa']} {m['away']}\n"
                f"🏆 {m['league']}"
            )
            events_posted.add(key)

    save(FILES["events"], list(events_posted))

# ================= MAIN =================
async def main():
    await startup()
    async with aiohttp.ClientSession() as session:
        while True:
            await post_today(session)
            await hourly_live(session)
            await halftime_events(session)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
