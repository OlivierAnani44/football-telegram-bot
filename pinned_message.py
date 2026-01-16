from telegram import Bot


PINNED_TEXT = """
🎁 **BONUS OFFICIEL – 1xBet**

💰 Bookmaker partenaire : **1xBet**
🎁 Code promo : **XPVIP**

👉 Pariez ici :
https://refpa58144.com/L?tag=d_5133758m_4129c_&site=5133758&ad=4129

⚠️ Jouez responsablement (18+)
"""

def pin_message(bot: Bot, channel_id):
    msg = bot.send_message(
        chat_id=channel_id,
        text=PINNED_TEXT,
        parse_mode="Markdown"
    )
    bot.pin_chat_message(
        chat_id=channel_id,
        message_id=msg.message_id,
        disable_notification=True
    )



