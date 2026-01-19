import os
import asyncio
import httpx
import logging
from datetime import date

# ================= CONFIG =================
SPORTMONKS_API_TOKEN = os.getenv("SPORTMONKS_API_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # @channel ou chat_id

# ================= INIT =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FootballBot")

# ================= UTIL =================
def check_tokens():
    missing = []
    if not SPORTMONKS_API_TOKEN:
        missing.append("SPORTMONKS_API_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise RuntimeError(f"⚠️ Les variables suivantes sont manquantes : {', '.join(missing)}")

async def send_message(text: str):
    """Envoi d'un message Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            })
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur Telegram : {e.response.status_code} - {e.response.text}")

async def sportmonks_get(endpoint: str, params: dict = None):
    """Requête vers SportMonks API."""
    if params is None:
        params = {}
    params["api_token"] = SPORTMONKS_API_TOKEN
    url = f"https://soccer.sportmonks.com/api/v3/football/{endpoint}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

# ================= LOGIQUE =================
async def post_today():
    today = date.today().isoformat()
    try:
        data = await sportmonks_get(f"fixtures/date/{today}", params={
            "include": "localTeam,visitorTeam,highlights,scores"
        })
        fixtures = data.get("data", [])
        if not fixtures:
            await send_message("⚠️ Aucune donnée pour aujourd'hui.")
            return

        lines = []
        for f in fixtures[:10]:  # limiter à 10 matchs
            home = f.get("localTeam", {}).get("data", {}).get("name", "Home")
            away = f.get("visitorTeam", {}).get("data", {}).get("name", "Away")
            score_home = f.get("scores", {}).get("localteam_score", "-")
            score_away = f.get("scores", {}).get("visitorteam_score", "-")
            highlight = f.get("highlights", {}).get("data", [{}])[0].get("url", "")

            line = f"⚽ {home} {score_home}–{score_away} {away}"
            if highlight:
                line += f"\n🎥 [Vidéo du but]({highlight})"
            lines.append(line)

        await send_message("*MATCHS DU JOUR:*\n\n" + "\n\n".join(lines))
    except httpx.HTTPStatusError as e:
        await send_message(f"⚠️ Erreur SportMonks : {e.response.status_code} - {e.response.text}")
    except Exception as e:
        await send_message(f"⚠️ Erreur inattendue : {e}")

# ================= MAIN =================
async def main():
    try:
        check_tokens()
        await send_message("🚀 Bot football démarré ✅")
        await post_today()
    except RuntimeError as e:
        logger.error(e)
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
