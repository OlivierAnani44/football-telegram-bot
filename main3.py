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

LIVE_URL = "https://m.flashscore.com/"
POSTED_FILE = "posted_live.json"
STARTUP_FILE = "startup.json"

DEFAULT_IMAGE = "https://i.imgur.com/8QfYJZK.jpg"

ALLOWED_LEAGUES = [
    "Premier League",
    "Ligue 1",
    "LaLiga",
    "Serie A",
    "Bundesliga",
    "Champions League",
    "CAF"
]

# ================= INIT =================
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ================= STORAGE =================
def load_set(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_set(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(list(data), f)

posted = load_set(POSTED_FILE)

# ================= STARTUP =================
def has_started():
    return os.path.exists(STARTUP_FILE)

def mark_started():
    with open(STARTUP_FILE, "w", encoding="utf-8") as f:
        json.dump({"started": True}, f)

async def startup_message():
    msg = (
        "👋 *Salut tout le monde !*\n\n"
        "⚽ Le bot football est maintenant *actif*.\n"
        "• Buts en direct\n"
        "• Mi-temps & fin de match\n"
        "• Pronostics live\n\n"
        "🔥 Restez connectés !"
    )
    for ch in CHANNELS:
        await bot.send_message(chat_id=ch, text=msg, parse_mode="Markdown")
        await asyncio.sleep(2)

# ================= PRONOSTIC =================
def pronostic(sh, sa):
    if sh > sa:
        res, cote = "1️⃣ Victoire Domicile", "1.45"
    elif sa > sh:
        res, cote = "2️⃣ Victoire Extérieur", "2.90"
    else:
        res, cote = "❌ Match Nul", "3.10"

    btts = "✅ OUI" if sh > 0 and sa > 0 else "❌ NON"
    over = "🔼 Over 2.5" if sh + sa >= 3 else "🔽 Under 2.5"
    return res, cote, btts, over

# ================= SCRAP LIVE =================
async def scrape_matches(session):
    matches = []

    async with session.get(
        LIVE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 10)",
            "Accept-Language": "fr-FR,fr;q=0.9"
        }
    ) as r:
        soup = BeautifulSoup(await r.text(), "html.parser")

        for row in soup.select("div.event"):
            try:
                home = row.select_one(".event__participant--home").text.strip()
                away = row.select_one(".event__participant--away").text.strip()

                scores = row.select(".event__score")
                if len(scores) < 2:
                    continue

                sh = int(scores[0].text.strip())
                sa = int(scores[1].text.strip())

                minute = row.select_one(".event__time").text.strip()
                league = row.find_previous("div", class_="event__title").text.strip()

                if not any(l.lower() in league.lower() for l in ALLOWED_LEAGUES):
                    continue

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

    logger.info(f"⚽ Matchs détectés : {len(matches)}")
    return matches

# ================= MESSAGE =================
def build_message(m, event):
    res, cote, btts, over = pronostic(m["sh"], m["sa"])
    return (
        f"⚽ *{event}*\n\n"
        f"🏆 *{m['league']}*\n\n"
        f"⚔️ *{m['home']}* {m['sh']} – {m['sa']} *{m['away']}*\n"
        f"⏱ {m['minute']}\n\n"
        f"🧠 *Pronostics Live*\n"
        f"{res} | 💰 {cote}\n"
        f"BTTS : {btts}\n"
        f"{over}\n\n"
        f"🕒 {datetime.now().strftime('%H:%M')}\n"
        f"#Football #Live"
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

# ================= LOOP =================
async def live_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            matches = await scrape_matches(session)

            for m in matches:
                base = f"{m['home']}-{m['away']}"

                # ⚽ BUT
                goal_key = f"{base}-{m['sh']}-{m['sa']}"
                if goal_key not in posted:
                    await post(DEFAULT_IMAGE, build_message(m, "BUT ⚽"))
                    posted.add(goal_key)
                    save_set(POSTED_FILE, posted)

                # ⏸ MI-TEMPS
                if "HT" in m["minute"]:
                    ht_key = f"{base}-HT"
                    if ht_key not in posted:
                        await post(DEFAULT_IMAGE, build_message(m, "MI-TEMPS ⏸"))
                        posted.add(ht_key)
                        save_set(POSTED_FILE, posted)

                # 🏁 FIN
                if "FT" in m["minute"]:
                    ft_key = f"{base}-FT"
                    if ft_key not in posted:
                        await post(DEFAULT_IMAGE, build_message(m, "FIN DU MATCH 🏁"))
                        posted.add(ft_key)
                        save_set(POSTED_FILE, posted)

            await asyncio.sleep(60)

# ================= MAIN =================
async def main():
    logger.info("⚽ BOT FOOTBALL LIVE DÉMARRÉ")

    if not has_started():
        await startup_message()
        mark_started()

    await live_loop()

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN ou CHANNELS manquant")
        exit(1)

    asyncio.run(main())
