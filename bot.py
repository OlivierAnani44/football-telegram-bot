from telegram import Bot
import schedule
import time
from sources import fetch_news
from formatter import format_post
from scores import get_today_matches
from scores_live import check_live_goals
from red_cards import check_red_cards
from match_summary import fetch_finished_matches, generate_summary
from pinned_message import pin_message

BOT_TOKEN = "TON_TOKEN_ICI"
CHANNEL_ID = "@TonCanalTelegram"



bot = Bot(BOT_TOKEN)
posted = set()

pin_message(bot, CHANNEL_ID)

def publish_news():
    news = fetch_news()

    for item in news:
        if item["link"] in posted:
            continue

        message, image = format_post(item)

        if image:
            bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image,
                caption=message,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode="Markdown"
            )

        posted.add(item["link"])
        time.sleep(4)

def publish_matches():
    matches = get_today_matches()
    if matches:
        bot.send_message(
            chat_id=CHANNEL_ID,
            text=matches,
            parse_mode="Markdown"
        )

def live_alerts():
    alerts = check_live_goals()
    for alert in alerts:
        bot.send_message(CHANNEL_ID, alert, parse_mode="Markdown")

def red_card_alerts():
    alerts = check_red_cards()
    for a in alerts:
        bot.send_message(CHANNEL_ID, a, parse_mode="Markdown")

def publish_summaries():
    matches = fetch_finished_matches()

    for m in matches:
        match_id = m["fixture"]["id"]
        if match_id in posted:
            continue

        summary = generate_summary(m)
        bot.send_message(CHANNEL_ID, summary, parse_mode="Markdown")

        posted.add(match_id)

schedule.every(15).minutes.do(publish_summaries)


schedule.every(1).minutes.do(red_card_alerts)


schedule.every(1).minutes.do(live_alerts)

schedule.every(30).minutes.do(publish_news)
schedule.every().day.at("10:00").do(publish_matches)

print("🤖 BOT FOOTBALL PRO LANCÉ")
while True:
    schedule.run_pending()
    time.sleep(1)


git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/OlivierAnani44/football-telegram-bot.git
git push -u origin main
