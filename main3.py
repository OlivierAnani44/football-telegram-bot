import os, asyncio, aiohttp, json, logging, random
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS").split(",") if c.strip()]
LIVE_URL = "https://www.flashscore.com/"
POSTED_FILE = "posted_live.json"

DEFAULT_IMAGE = "https://i.imgur.com/8QfYJZK.jpg"

ALLOWED_LEAGUES = [
    "Premier League", "LaLiga", "Serie A",
    "Bundesliga", "Ligue 1", "Champions League", "CAF"
]

bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballUltimateBot")

# ---------------- STORAGE ----------------
def load_data():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_data(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(data), f)

posted = load_data()

# ---------------- PRONOSTIC ----------------
def pronostic(sh, sa):
    if sh > sa:
        res = "1️⃣ Victoire Domicile"
        cote = "1.45"
    elif sa > sh:
        res = "2️⃣ Victoire Extérieur"
        cote = "2.90"
    else:
        res = "❌ Match Nul"
        cote = "3.10"

    btts = "✅ OUI" if sh > 0 and sa > 0 else "❌ NON"
    over = "🔼 Over 2.5" if sh + sa >= 3 else "🔽 Under 2.5"

    return res, cote, btts, over

# ---------------- SCRAP ----------------
async def scrape(session):
    async with session.get(LIVE_URL, headers={"User-Agent": "Mozilla/5.0"}) as r:
        soup = BeautifulSoup(await r.text(), "html.parser")
        matches = []

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

# ---------------- MESSAGE ----------------
def build_message(m, event):
    res, cote, btts, over = pronostic(m["sh"], m["sa"])

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

# ---------------- POST ----------------
async def post(photo, text):
    for ch in CHANNELS:
        await bot.send_photo(
            chat_id=ch,
            photo=photo,
            caption=text,
            parse_mode="Markdown"
        )
        await asyncio.sleep(2)

# ---------------- LOOP ----------------
async def live_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            matches = await scrape(session)

            for m in matches:
                base_key = f"{m['home']}-{m['away']}"

                # ⚽ BUT
                goal_key = f"{base_key}-{m['sh']}-{m['sa']}"
                if goal_key not in posted:
                    await post(DEFAULT_IMAGE, build_message(m, "BUT ⚽"))
                    posted.add(goal_key)
                    save_data(posted)

                # ⏸ MI-TEMPS
                if "HT" in m["minute"]:
                    ht_key = f"{base_key}-HT"
                    if ht_key not in posted:
                        await post(DEFAULT_IMAGE, build_message(m, "MI-TEMPS ⏸"))
                        posted.add(ht_key)
                        save_data(posted)

                # 🏁 FIN
                if "FT" in m["minute"]:
                    ft_key = f"{base_key}-FT"
                    if ft_key not in posted:
                        await post(DEFAULT_IMAGE, build_message(m, "FIN DU MATCH 🏁"))
                        posted.add(ft_key)
                        save_data(posted)

            await asyncio.sleep(60)

# ---------------- MAIN ----------------
async def main():
    logger.info("⚽ BOT FOOTBALL ULTIME DÉMARRÉ")
    await live_loop()

if __name__ == "__main__":
    asyncio.run(main())
