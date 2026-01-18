import os
import asyncio
import aiohttp
import json
import logging
import random
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

LIVE_URL = "https://www.flashscore.com/"
POSTED_FILE = "posted_live.json"
STARTUP_FILE = "startup.json"

DEFAULT_IMAGE = "https://i.imgur.com/8QfYJZK.jpg"

ALLOWED_LEAGUES = [
    "Premier League",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Champions League",
    "CAF"
]

# ================= INIT =================
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballUltimateBot")

# ================= STORAGE =================
def load_set(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_set(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(list(data), f)

posted_events = load_set(POSTED_FILE)

# ================= STARTUP =================
def has_started_before():
    return os.path.exists(STARTUP_FILE)

def mark_started():
    with open(STARTUP_FILE, "w", encoding="utf-8") as f:
        json.dump({"started": True}, f)

async def send_startup_message():
    message = (
        "👋 *Salut tout le monde !*\n\n"
        "⚽ Je suis désormais *actif* et je vous enverrai :\n"
        "• ⚽ Les buts en direct\n"
        "• ⏸ Mi-temps & 🏁 fin de match\n"
        "• 🧠 Pronostics live\n"
        "• 📊 Scores en temps réel\n\n"
        "🔥 Restez connectés !"
    )
    for ch in CHANNELS:
        await bot.send_message(chat_id=ch, text=message, parse_mode="Markdown")
        await asyncio.sleep(2)

# ================= PRONOSTIC =================
def generate_pronostic(sh, sa):
    if sh > sa:
        result = "1️⃣ Victoire Domicile"
        cote = "1.45"
    elif sa > sh:
        result = "2️⃣ Victoire Extérieur"
        cote = "2.90"
    else:
        result = "❌ Match Nul"
        cote = "3.10"

    btts = "✅ OUI" if sh > 0 and sa > 0 else "❌ NON"
    over = "🔼 Over 2.5" if sh + sa >= 3 else "🔽 Under 2.5"

    return result, cote, btts, over

# ================= SCRAP =================
async def scrape_live_matches(session):
    matches = []
    async with session.get(LIVE_URL, headers={"User-Agent": "Mozilla/5.0"}) as r:
        soup = BeautifulSoup(await r.text(), "html.parser")

        for m in soup.select(".event__match"):
            try:
                league = m.find_previous("div", class_="event__title").text.strip()
                if not any(l in league for l in ALLOWED_LEAGUES):
                    continue

                home = m.select_one(".event__participant--home").text.strip()
                away = m.select_one(".event__participant--away").text.strip()
                sh = int(m.select_one(".event__score--home").text)
                sa = int(m.select_one(".event__score--away").text)
                minute = m.select_one(".event__stage").text.strip()

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

# ================= MESSAGE =================
def build_message(m, event):
    res, cote, btts, over = generate_pronostic(m["sh"], m["sa"])

    return (
        f"⚽ *{event}*\n\n"
        f"🏆 *{m['league']}*\n\n"
        f"⚔️ *{m['home']}* {m['sh']} – {m['sa']} *{m['away']}*\n"
        f"⏱ {m['minute']}\n\n"
        f"🧠 *Pronostics Live*\n"
        f"{res} | 💰 Cote ~ {cote}\n"
        f"BTTS : {btts}\n"
        f"{over}\n\n"
        f"🕒 {datetime.now().strftime('%H:%M')}\n"
        f"#Football #Live #Pronostic"
    )

# ================= POST =================
async def post(photo, text):
    for ch in CHANNELS:
        await bot.send_photo(
            chat_id=ch,
            photo=photo,
            caption=text,
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)

# ================= MAIN LOOP =================
async def live_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            matches = await scrape_live_matches(session)

            for m in matches:
                base_key = f"{m['home']}-{m['away']}"

                # ⚽ BUT
                goal_key = f"{base_key}-{m['sh']}-{m['sa']}"
                if goal_key not in posted_events:
                    await post(DEFAULT_IMAGE, build_message(m, "BUT ⚽"))
                    posted_events.add(goal_key)
                    save_set(POSTED_FILE, posted_events)

                # ⏸ MI-TEMPS
                if "HT" in m["minute"]:
                    ht_key = f"{base_key}-HT"
                    if ht_key not in posted_events:
                        await post(DEFAULT_IMAGE, build_message(m, "MI-TEMPS ⏸"))
                        posted_events.add(ht_key)
                        save_set(POSTED_FILE, posted_events)

                # 🏁 FIN
                if "FT" in m["minute"]:
                    ft_key = f"{base_key}-FT"
                    if ft_key not in posted_events:
                        await post(DEFAULT_IMAGE, build_message(m, "FIN DU MATCH 🏁"))
                        posted_events.add(ft_key)
                        save_set(POSTED_FILE, posted_events)

            await asyncio.sleep(60)

# ================= RUN =================
async def main():
    logger.info("⚽ BOT FOOTBALL ULTIME DÉMARRÉ")

    if not has_started_before():
        await send_startup_message()
        mark_started()

    await live_loop()

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN ou CHANNELS manquant")
        exit(1)

    asyncio.run(main())
