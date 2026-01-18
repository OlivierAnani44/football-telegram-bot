import os
import json
import asyncio
import logging
from playwright.async_api import async_playwright
import httpx
from datetime import datetime

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

BESOCCER_URL = "https://www.besoccer.com/livescore"
POSTED_FILE = "posted.json"

CHECK_INTERVAL = 300  # 5 minutes

# ================= LOG =================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BeSoccerBot")

# ================= UTILS =================
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted(data):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(data), f)

# ================= TELEGRAM =================
async def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()

# ================= SCRAPER =================
async def scrape_matches():
    matches = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        await page.goto(BESOCCER_URL, timeout=60000)
        await page.wait_for_timeout(5000)

        rows = await page.query_selector_all("div.match-row")

        for row in rows:
            try:
                time = await row.query_selector(".time")
                teams = await row.query_selector_all(".team-name")
                score = await row.query_selector(".marker")

                if not teams or len(teams) < 2:
                    continue

                home = (await teams[0].inner_text()).strip()
                away = (await teams[1].inner_text()).strip()
                match_time = (await time.inner_text()).strip() if time else "?"
                match_score = (await score.inner_text()).strip() if score else "-"

                match_id = f"{home}-{away}-{match_time}"

                matches.append({
                    "id": match_id,
                    "home": home,
                    "away": away,
                    "time": match_time,
                    "score": match_score
                })
            except Exception:
                continue

        await browser.close()

    logger.info(f"Scraped {len(matches)} matches")
    return matches

# ================= MAIN LOGIC =================
async def process_matches():
    posted = load_posted()
    matches = await scrape_matches()

    new_posts = 0

    for m in matches:
        if m["id"] in posted:
            continue

        message = (
            f"⚽ {m['home']} vs {m['away']}\n"
            f"🕒 {m['time']}\n"
            f"📊 Score: {m['score']}\n\n"
            f"🔗 https://www.besoccer.com"
        )

        await send_message(message)
        posted.add(m["id"])
        new_posts += 1

        await asyncio.sleep(3)

    if new_posts:
        save_posted(posted)
        logger.info(f"Posted {new_posts} new matches")
    else:
        logger.info("No new matches")

# ================= LOOP =================
async def main():
    await send_message("🚀 BeSoccer Bot started")
    while True:
        try:
            await process_matches()
        except Exception as e:
            logger.error(f"Main loop error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
