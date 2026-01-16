from telegram_pub import publish_telegram
from whatsapp_pub import publish_whatsapp
from twitter_pub import publish_twitter

def publish_everywhere(bot, channel, text, image=None):
    publish_telegram(bot, channel, text, image)
    publish_whatsapp(text)
    publish_twitter(text)
