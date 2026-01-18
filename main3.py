import os
import asyncio
import json
import logging
from datetime import datetime, date
from telegram import Bot
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

LEQUIPE_URL = "https://www.lequipe.fr/Football/Directs"

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
        await asyncio.sleep(1)

# ================= STARTUP =================
async def startup():
    if not os.path.exists(FILES["startup"]):
        await send(
            "👋 *Salut tout le monde !*\n\n"
            "⚽ Bot Football *ACTIF*\n"
            "• Matchs du jour (L’Équipe)\n"
            "• Live toutes les 1h\n"
            "• Mi‑temps & scores\n\n"
            "🔥 Bon match à tous"
        )
        save(FILES["startup"], {"ok": True})

# ================= FETCH MATCHES =================
async def fetch_matches(page):
    await page.goto(LEQUIPE_URL)
    await page.wait_for_timeout(5000)  # 5 secondes pour charger JS
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    matches = []

    for block in soup.select("div.match-block, div.DirectMatch"):
        try:
            home = block.select_one(".teamHome, .team.home").get_text(strip=True)
            away = block.select_one(".teamAway, .team.away").get_text(strip=True)
            score_text = block.select_one(".score").get_text(strip=True) if block.select_one(".score") else "-"
            if "-" in score_text:
                sh, sa = [s.strip() for s in score_text.split("-")]
            else:
                sh, sa = "-", "-"
            minute = block.select_one(".minute").get_text(strip=True) if block.select_one(".minute") else "?"
            league = block.select_one(".competition").get_text(strip=True) if block.select_one(".competition") else "Football"

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
async def post_today(page):
    state = load(FILES["today"], {})
    if state.get("date") == str(date.today()):
        return

    matches = await fetch_matches(page)
    if not matches:
        return

    lines = [f"⚔️ {m['home']} vs {m['away']}" for m in matches[:20]]
    await send(f"📅 *MATCHS DU JOUR ({date.today().strftime('%d/%m')})*\n\n" + "\n".join(lines))
    save(FILES["today"], {"date": str(date.today())})

# ================= LIVE HORAIRE =================
async def hourly_live(page):
    hour = datetime.now().strftime("%Y-%m-%d-%H")
    state = load(FILES["hour"], {})
    if state.get("hour") == hour:
        return

    matches = await fetch_matches(page)
    logger.info(f"⚽ Live détectés : {len(matches)}")
    if not matches:
        return

    lines = [f"🔴 {m['home']} {m['sh']}–{m['sa']} {m['away']} ({m['minute']})" for m in matches[:15]]
    await send("🔴 *MATCHS EN COURS*\n\n" + "\n".join(lines))
    save(FILES["hour"], {"hour": hour})

# ================= MI‑TEMPS =================
async def halftime_events(page):
    matches = await fetch_matches(page)
    for m in matches:
        if m["minute"].lower() in ["mi‑temps", "ht"]:
            key = f"{m['home']}-{m['away']}-HT"
            if key in events_posted:
                continue
            await send(f"⏸ *MI‑TEMPS*\n\n{m['home']} {m['sh']}–{m['sa']} {m['away']}\n🏆 {m['league']}")
            events_posted.add(key)
    save(FILES["events"], list(events_posted))

# ================= MAIN =================
async def main():
    await startup()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        while True:
            await post_today(page)
            await hourly_live(page)
            await halftime_events(page)
            await asyncio.sleep(60)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
