import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_URL = os.getenv("GROQ_API_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Salut ! Je suis ton bot de pronostics football.\n"
        "Envoie /matches pour voir les matchs favoris d'aujourd'hui."
    )

async def matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = requests.get(f"{GROQ_API_URL}/matches/favorites",
                            headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
    if response.status_code != 200:
        await update.message.reply_text("❌ Impossible de récupérer les matchs pour le moment.")
        return

    matchs = response.json()[:10]
    if not matchs:
        await update.message.reply_text("Aucun match disponible aujourd'hui 😔")
        return

    keyboard = []
    for match in matchs:
        emoji = "🔥" if match.get("is_hot") else "⚽"
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {match['home']} vs {match['away']} ({match['time']})",
                callback_data=match['id']
            )
        ])

    await update.message.reply_text(
        "Voici les matchs les plus importants du jour, choisis-en un :",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def match_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    match_id = query.data

    response = requests.get(f"{GROQ_API_URL}/matches/{match_id}/analysis",
                            headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
    if response.status_code != 200:
        await query.edit_message_text("❌ Impossible de récupérer l'analyse pour ce match.")
        return

    data = response.json()
    analyse_text = (
        f"📊 <b>Analyse :</b> {data['home']} vs {data['away']}\n\n"
        f"🕒 Heure : {data.get('time','N/A')}\n"
        f"🌟 Contexte : {data.get('context','N/A')}\n"
        f"💪 Forme : {data.get('form','N/A')}\n\n"
        f"📈 Probabilités :\n"
        f"🏠 {data.get('home')} : {data.get('prob_home','?')}%\n"
        f"🤝 Nul : {data.get('prob_draw','?')}%\n"
        f"🏃 {data.get('away')} : {data.get('prob_away','?')}%\n\n"
        f"🎯 Pronostic : {data.get('prediction','N/A')}\n"
        f"💡 Conseil : {data.get('advice','N/A')}"
    )
    await query.edit_message_text(analyse_text, parse_mode="HTML")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("matches", matches))
    app.add_handler(CallbackQueryHandler(match_analysis))
    print("Bot démarré...")
    app.run_polling()
