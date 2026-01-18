import os
import asyncio
import logging
import httpx
from datetime import datetime

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

API_BASE = "https://www.thesportsdb.com/api/v1/json/3"
TEST_DATE = "2024-06-15"  # DATE CONNUE AVEC DES MATCHS
SPORT = "Soccer"

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ================= TELEGRAM =================
async def send_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHANNEL_ID,
        "text": text
        # ❌ PAS de parse_mode
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)

        if r.status_code != 200:
            logger.error(f"Telegram ERROR {r.status_code}: {r.text}")
        else:
            logger.info("Message envoyé")

# ================= API =================
async def api_get(endpoint: str, params: dict):
    url = f"{API_BASE}/{endpoint}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, timeout=20)
        if r.status_code != 200:
            logger.error(f"API ERROR {r.status_code}")
            return None
        try:
            return r.json()
        except Exception:
            logger.error("Réponse non JSON")
            return None

# ================= LOGIC =================
async def post_matches():
    logger.info(f"Test avec la date : {TEST_DATE}")

    data = await api_get(
        "eventsday.php",
        {"d": TEST_DATE, "s": SPORT}
    )

    if not data or not data.get("events"):
        logger.info("Aucun match trouvé")
        await send_message("😴 Aucun match détecté pour le test.")
        return

    for event in data["events"][:5]:  # limite 5 pour test
        home = event["strHomeTeam"]
        away = event["strAwayTeam"]
        time = event.get("strTime", "??:??")
        league = event.get("strLeague", "Football")

        msg = (
            f"⚽ <b>{league}</b>\n"
            f"{home} 🆚 {away}\n"
            f"🕒 {time}\n"
            f"📅 {TEST_DATE}"
        )

        await send_message(msg)
        await asyncio.sleep(2)

# ================= MAIN =================
async def main():
    await send_message("🚀 Bot football démarré (mode TEST)")
    await post_matches()

if __name__ == "__main__":
    asyncio.run(main())
