import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

def send_telegram(message):
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Variables BOT_TOKEN ou CHANNEL_ID manquantes")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        print(f"[TELEGRAM] status={resp.status_code} response={resp.text}")
    else:
        print("[TELEGRAM] Message envoyé ✅")
