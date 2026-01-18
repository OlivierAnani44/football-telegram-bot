import os
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, date
from bs4 import BeautifulSoup
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

BASE_URL = "https://m.flashscore.com/"

FILES = {
    "startup": "startup.json",
    "today": "today.json",
    "hour": "hour.json",
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

# ================= SCRAPING =================
async def fetch(session):
    async with session.get(
        BASE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Android)",
            "Accept-Language": "fr-FR,fr;q=0.9"
        }
    ) as r:
        return BeautifulSoup(await r.text(), "html.parser")

def parse_matches(soup):
    matches = []
    for row in soup.select("div.event"):
        try:
            home = row.select_one(".event__participant--home").text.strip()
            away = row.select_one(".event__participant--away").text.strip()

            scores = row.select(".event__score span")
            if len(scores) < 2:
                sh, sa = "-", "-"
            else:
                sh, sa = scores[0].text.strip(), scores[1].text.strip()

            stage = row.select_one(".event__stage")
            minute = stage.text.strip() if stage else "?"

            league = row.find_previous("div", class_="event__title")
            league = league.text.strip() if league else "Football"

            matches.append({
                "home": home,
                "away": away,
                "sh": sh,
                "sa": sa,
                "minute": minute,
                "league": league
            })
        except:
            continue

    return matches

# ================= MATCHS DU JOUR =================
async def post_today(session):
    state = load(FILES["today"], {})
    if state.get("date") == str(date.today()):
        return

    soup = await fetch(session)
    matches = parse_matches(soup)

    if not matches:
        return

    lines = [
        f"⚔️ {m['home']} vs {m['away']}"
        for m in matches[:20]
    ]

    await send(
        f"📅 *MATCHS DU JOUR ({date.today().strftime('%d/%m')})*\n\n"
        + "\n".join(lines)
    )

    save(FILES["today"], {"date": str(date.today())})

# ================= LIVE HORAIRE =================
async def hourly_live(session):
    hour = datetime.now().strftime("%Y-%m-%d-%H")
    state = load(FILES["hour"], {})

    if state.get("hour") == hour:
        return

    soup = await fetch(session)
    matches = parse_matches(soup)
    logger.info(f"⚽ Live détectés : {len(matches)}")

    if not matches:
        return

    lines = [
        f"🔴 {m['home']} {m['sh']}–{m['sa']} {m['away']} ({m['minute']})"
        for m in matches[:15]
    ]

    await send(
        "🔴 *MATCHS EN COURS*\n\n" + "\n".join(lines)
    )

    save(FILES["hour"], {"hour": hour})

# ================= MI-TEMPS =================
async def halftime_events(session):
    soup = await fetch(session)
    matches = parse_matches(soup)

    for m in matches:
        if m["minute"] == "HT":
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
