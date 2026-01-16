def publish_telegram(bot, channel, text, image=None):
    if image:
        bot.send_photo(channel, image, caption=text, parse_mode="Markdown")
    else:
        bot.send_message(channel, text, parse_mode="Markdown")
