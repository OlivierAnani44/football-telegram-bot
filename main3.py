import os
import asyncio
import httpx
import json
from datetime import date

SPORTMONKS_TOKEN = os.getenv("SPORTMONKS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

POSTED_FILE = "posted.json"

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return json.load(f)
    return []

def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(data, f)

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as c:
        await c.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        })

async def send_photo(photo_url, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as c:
        await c.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": "HTML"
        })

async def sportmonks_get(endpoint):
    url = f"https://api.sportmonks.com/v3/football/{endpoint}"
    params = {"api_token": SPORTMONKS_TOKEN}
    async with httpx.AsyncClient() as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()

async def post_matches_today():
    posted = load_posted()
    today_str = date.today().isoformat()

    try:
        data = await sportmonks_get(f"fixtures/date/{today_str}?include=participants,events,scores")
    except httpx.HTTPStatusError as e:
        await send_telegram(f"⚠️ SportMonks error: {e.response.status_code}")
        return

    fixtures = data.get("data", [])
    if not fixtures:
        await send_telegram(f"📅 Aucun match trouvé pour {today_str}")
        return

    for match in fixtures:
        mid = match["id"]
        if mid in posted:
            continue

        name = match.get("name") or ""
        start = match.get("starting_at") or ""
        state_id = match.get("state_id", 0)

        scores = match.get("scores", {})
        sh = scores.get("localteam_score", "-")
        sa = scores.get("visitorteam_score", "-")

        msg = f"⚽ {name} \n🕒 {start}\nScore: {sh}-{sa}"
        await send_telegram(msg)

        # highlights/events
        events = match.get("events", [])
        for ev in events:
            if ev.get("type") == "goal":
                video = ev.get("video") or ev.get("details", {}).get("media_url")
                if video:
                    await send_photo(video, caption=f"🎯 But: {name}")

        posted.append(mid)

    save_posted(posted)

async def main_loop():
    while True:
        await post_matches_today()
        await asyncio.sleep(600)  # toutes les 10 minutes

if __name__ == "__main__":
    asyncio.run(main_loop())
