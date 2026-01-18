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

LIVE_URL = "https://m.flashscore.com/live/"
TODAY_URL = "https://m.flashscore.com/"

POSTED_FILE = "posted.json"
STARTUP_FILE = "startup.json"
HOURLY_FILE = "hourly.json"
TODAY_FILE = "today.json"

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

posted = set(load(POSTED_FILE, []))

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
    if not os.path.exists(STARTUP_FILE):
        await send(
            "👋 *Salut tout le monde !*\n\n"
            "⚽ Bot football *ACTIF*\n"
            "• Matchs du jour\n"
            "• Lives toutes les 1h\n"
            "• Buts & mi-temps\n\n"
            "🔥 Restez connectés"
        )
        save(STARTUP_FILE, {"started": True})

# ================= SCRAPE MATCHS DU JOUR =================
async def scrape_today(session):
    matches = []
    async with session.get(
        TODAY_URL,
        headers={"User-Agent": "Mozilla/5.0 (Android)"}
    ) as r:
        soup = BeautifulSoup(await r.text(), "html.parser")

        for row in soup.select("div.event__match"):
            try:
                home = row.select_one(".event__participant--home").text.strip()
                away = row.select_one(".event__participant--away").text.strip()
                time = row.select_one(".event__time").text.strip()
                league = row.find_previous("div", class_="event__title").text.strip()

                matches.append(f"🕒 {time} — *{home} vs {away}*")

            except:
                continue
    return matches

# ================= SCRAPE LIVE =================
async def scrape_live(session):
    matches = []
    async with session.get(
        LIVE_URL,
        headers={"User-Agent": "Mozilla/5.0 (Android)"}
    ) as r:
        soup = BeautifulSoup(await r.text(), "html.parser")

        for row in soup.select("div.event__match"):
            try:
                home = row.select_one(".event__participant--home").text.strip()
                away = row.select_one(".event__participant--away").text.strip()
                sh = row.select_one(".event__score--home").text.strip()
                sa = row.select_one(".event__score--away").text.strip()
                minute = row.select_one(".event__stage").text.strip()

                matches.append({
                    "home": home,
                    "away": away,
                    "sh": sh,
                    "sa": sa,
                    "minute": minute
                })
            except:
                continue
    logger.info(f"⚽ Live détectés : {len(matches)}")
    return matches

# ================= MATCHS DU JOUR (1 FOIS / JOUR) =================
async def post_today(session):
    today_state = load(TODAY_FILE, {})
    if today_state.get("date") == str(date.today()):
        return

    matches = await scrape_today(session)
    if not matches:
        return

    text = (
        f"📅 *MATCHS DU JOUR ({date.today().strftime('%d/%m')})*\n\n"
        + "\n".join(matches[:20])
        + "\n\n#Football"
    )

    await send(text)
    save(TODAY_FILE, {"date": str(date.today())})

# ================= LIVE TOUTES LES 1 HEURE =================
async def hourly_live(session):
    hour = datetime.now().strftime("%Y-%m-%d-%H")
    hourly_state = load(HOURLY_FILE, {})

    if hourly_state.get("hour") == hour:
        return

    matches = await scrape_live(session)
    if not matches:
        return

    lines = [
        f"⚔️ {m['home']} {m['sh']}–{m['sa']} {m['away']} ({m['minute']})"
        for m in matches
    ]

    text = (
        "🔴 *MATCHS EN LIVE*\n\n"
        + "\n".join(lines[:15])
        + "\n\n⏱ Mise à jour horaire"
    )

    await send(text)
    save(HOURLY_FILE, {"hour": hour})

# ================= EVENTS LIVE =================
async def live_events(session):
    matches = await scrape_live(session)

    for m in matches:
        key = f"{m['home']}-{m['away']}-{m['sh']}-{m['sa']}-{m['minute']}"

        # MI-TEMPS
        if m["minute"] == "HT" and key not in posted:
            await send(
                f"⏸ *MI-TEMPS*\n\n"
                f"{m['home']} {m['sh']}–{m['sa']} {m['away']}"
            )
            posted.add(key)

    save(POSTED_FILE, list(posted))

# ================= MAIN LOOP =================
async def main():
    await startup()

    async with aiohttp.ClientSession() as session:
        while True:
            await post_today(session)
            await hourly_live(session)
            await live_events(session)
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
