import os
import requests
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Token de ton bot Telegram
CHANNEL_ID = os.getenv("CHANNEL_ID")  # ID ou @nom_du_channel Telegram
GROQ_API_URL = os.getenv("GROQ_API_URL")  # URL de ton API GROQ
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Clé API GROQ

bot = Bot(token=BOT_TOKEN)

# ---------------- FONCTIONS ----------------
def get_top_matches():
    """Récupère les 10 meilleurs matchs du jour"""
    try:
        response = requests.get(
            f"{GROQ_API_URL}/matches/favorites",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"}
        )
        response.raise_for_status()
        return response.json()[:10]
    except Exception as e:
        print(f"Erreur récupération matchs : {e}")
        return []

def get_match_analysis(match_id):
    """Récupère l'analyse complète d'un match"""
    try:
        response = requests.get(
            f"{GROQ_API_URL}/matches/{match_id}/analysis",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erreur récupération analyse pour match {match_id} : {e}")
        return None

async def send_analysis_and_prediction():
    """Envoie automatiquement les analyses et pronostics"""
    matches = get_top_matches()
    if not matches:
        await bot.send_message(chat_id=CHANNEL_ID, text="Aucun match disponible aujourd'hui 😔")
        return

    for match in matches:
        data = get_match_analysis(match["id"])
        if not data:
            continue

        # ---------------- Analyse ----------------
        analyse_text = (
            f"📊 <b>Analyse du match :</b> {data['home']} vs {data['away']}\n"
            f"🕒 Heure : {data.get('time','N/A')}\n"
            f"🌟 Contexte : {data.get('context','N/A')}\n"
            f"💪 Forme : {data.get('form','N/A')}"
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=analyse_text, parse_mode=ParseMode.HTML)

        # Attente 1 minute avant le pronostic
        await asyncio.sleep(60)

        # ---------------- Pronostic ----------------
        pronostic_text = (
            f"🎯 <b>Pronostic :</b> {data.get('prediction','N/A')}\n"
            f"💡 Conseil : {data.get('advice','N/A')}\n"
            f"📈 Probabilités :\n"
            f"🏠 {data.get('home')} : {data.get('prob_home','?')}%\n"
            f"🤝 Nul : {data.get('prob_draw','?')}%\n"
            f"🏃 {data.get('away')} : {data.get('prob_away','?')}%"
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=pronostic_text, parse_mode=ParseMode.HTML)

# ---------------- BOUCLE PRINCIPALE ----------------
async def main():
    print(f"{datetime.now()} - Bot démarré, envoi des analyses du jour...")
    await send_analysis_and_prediction()
    print(f"{datetime.now()} - Toutes les analyses et pronostics ont été envoyés.")

if __name__ == "__main__":
    asyncio.run(main())
