import os
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime
import requests

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")       # Token Telegram
CHANNEL_ID = os.getenv("CHANNEL_ID")     # ID ou @nom_du_channel
GROQ_API_KEY = os.getenv("GROQ_API_KEY") # Clé API GROQ
DATASET = os.getenv("GROQ_DATASET", "production")  # Nom de la dataset

bot = Bot(token=BOT_TOKEN)

# ---------------- FONCTIONS ----------------
def check_groq_token():
    """Vérifie si le token GROQ est valide"""
    try:
        response = requests.post(
            f"https://api.sanity.io/v2021-10-21/data/query/{DATASET}",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"query": "*[_type=='match'][0..0]"}
        )
        if response.status_code == 401:
            print("❌ Erreur : Token GROQ invalide ou non autorisé !")
            return False
        return True
    except Exception as e:
        print(f"Erreur lors de la vérification du token : {e}")
        return False

def get_todays_matches():
    """Récupère les 10 meilleurs matchs du jour"""
    try:
        response = requests.post(
            f"https://api.sanity.io/v2021-10-21/data/query/{DATASET}",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "query": "*[_type=='match' && date == today()] | order(priority desc)[0..9]"
            }
        )
        response.raise_for_status()
        return response.json().get("result", [])
    except Exception as e:
        print(f"Erreur récupération matchs du jour : {e}")
        return []

def get_match_analysis(match_id):
    """Récupère l'analyse complète d'un match"""
    try:
        response = requests.post(
            f"https://api.sanity.io/v2021-10-21/data/query/{DATASET}",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "query": f"*[_type=='match' && _id=='{match_id}']{{home, away, time, context, form, prob_home, prob_draw, prob_away, prediction, advice}}"
            }
        )
        response.raise_for_status()
        data = response.json().get("result", [])
        return data[0] if data else None
    except Exception as e:
        print(f"Erreur récupération analyse match {match_id} : {e}")
        return None

async def send_matches():
    """Envoie analyse + pronostic pour chaque match du jour"""
    matches = get_todays_matches()
    if not matches:
        await bot.send_message(chat_id=CHANNEL_ID, text="Aucun match disponible aujourd'hui 😔")
        return

    for match in matches:
        match_id = match.get("_id")
        data = get_match_analysis(match_id)
        if not data:
            continue

        message_text = (
            f"⚽ <b>{data['home']} vs {data['away']}</b>\n\n"
            f"🕒 Heure : {data.get('time','N/A')}\n"
            f"🌟 Contexte : {data.get('context','N/A')}\n"
            f"💪 Forme : {data.get('form','N/A')}\n\n"
            f"📈 Probabilités :\n"
            f"🏠 {data.get('prob_home','?')}%\n"
            f"🤝 Nul : {data.get('prob_draw','?')}%\n"
            f"🏃 {data.get('prob_away','?')}%\n\n"
            f"🎯 Pronostic : {data.get('prediction','N/A')}\n"
            f"💡 Conseil : {data.get('advice','N/A')}"
        )

        await bot.send_message(chat_id=CHANNEL_ID, text=message_text, parse_mode=ParseMode.HTML)
        await asyncio.sleep(5)  # Pause pour éviter de spammer Telegram

# ---------------- BOUCLE PRINCIPALE ----------------
async def main():
    print(f"{datetime.now()} - Vérification du token GROQ...")
    if not check_groq_token():
        print("❌ Bot arrêté : Token GROQ invalide ou non autorisé")
        return

    print(f"{datetime.now()} - Envoi des analyses et pronostics du jour...")
    await send_matches()
    print(f"{datetime.now()} - Toutes les analyses ont été envoyées ✅")

if __name__ == "__main__":
    asyncio.run(main())
