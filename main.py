import os
import feedparser
import json
import asyncio
import logging
import re
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from bs4 import BeautifulSoup
import random
from datetime import datetime
import aiohttp

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNELS = os.getenv("CHANNELS")  # Séparés par des virgules, ex: @channel1,@channel2
CHANNELS = [c.strip() for c in CHANNELS.split(",") if c.strip()]

# Flux RSS francophones
RSS_FEEDS = [
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://rmcsport.bfmtv.com/rss/football/",
    "https://www.eurosport.fr/football/rss.xml",
    "https://www.20minutes.fr/sport/football/rss",
    "https://www.leparisien.fr/sports/football/rss.xml",
    "https://www.lefigaro.fr/sports/football/rss.xml",
    "https://www.footmercato.net/rss",
    "https://www.maxifoot.fr/rss.xml",
    "https://www.foot01.com/rss/football.xml",
    "https://www.france24.com/fr/sports/football/rss",
    "https://www.tf1info.fr/football/rss.xml",
    "https://www.bfmtv.com/rss/sports/football/",
    "https://www.ouest-france.fr/sport/football/rss.xml",
    "https://www.lavoixdunord.fr/sports/football/rss",
    "https://www.cahiersdufootball.net/rss.xml",
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Emojis
EMOJI_CATEGORIES = {
    'match': ['⚽', '🏆', '🆚', '🥅', '👕'],
    'transfert': ['🔄', '✍️', '📝', '💼', '💰'],
    'blessure': ['🤕', '🏥', '⚠️', '😔'],
    'championnat': ['🏅', '⭐', '👑', '🥇'],
    'coupe': ['🏆', '🥇', '🎖️'],
    'entraineur': ['👔', '📋', '🗣️'],
    'arbitrage': ['👨‍⚖️', '🟨', '🟥', '⏱️'],
    'jeune': ['🌟', '👶', '💫'],
    'contrat': ['📜', '💵', '✍️'],
    'general': ['📰', '🔥', '🚀', '💥']
}

PHRASES_ACCROCHE = {
    'exclusif': ["🚨 EXCLUSIF : ", "🎯 INFO EXCLUSIVE : ", "🔴 EXCLU TF1 : "],
    'breaking': ["🔥 BREAKING : ", "⚡ FLASH INFO : ", "💥 URGENT : "],
    'analyse': ["📊 ANALYSE : ", "🧠 DÉCRYPTAGE : ", "🔍 ENQUÊTE : "],
    'interview': ["🎤 INTERVIEW : ", "🗣️ TÉMOIGNAGE : ", "💬 CONFÉRENCE : "],
    'resultat': ["📈 RÉSULTAT : ", "🏁 FINAL : ", "✅ BILAN : "],
    'annonce': ["📢 ANNONCE : ", "🎊 RÉVÉLATION : ", "💎 SORTIE : "],
    'general': ["📰 INFO : ", "⚡ ACTU : ", "🔥 NOUVELLE : "]
}

HASHTAGS_FR = [
    "#Foot", "#Football", "#Ligue1", "#LigueDesChampions", "#CoupeDeFrance",
    "#PSG", "#OM", "#OL", "#LOSC", "#ASM", "#SRFC", "#FRA", "#TeamFrance",
    "#Mercato", "#Transfert", "#BallonDor", "#UEFA", "#ChampionsLeague"
]

# Initialisation bot
bot = Bot(token=BOT_TOKEN)

# ---------------- POSTÉ ----------------
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                links = set(json.load(f))
                if len(links) > MAX_POSTED_LINKS:
                    links = set(list(links)[-MAX_POSTED_LINKS:])
                logger.info(f"📁 {len(links)} liens chargés")
                return links
    except Exception as e:
        logger.error(f"❌ Erreur chargement: {e}")
    return set()

def save_posted_links():
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_links), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")

posted_links = load_posted_links()

# ---------------- UTILITAIRES ----------------
def clean_text(text, max_len=500):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text

def escape_markdown(text: str) -> str:
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)

# ---------------- ANALYSE ----------------
def analyze_content(title, summary):
    text = f"{title} {summary}".lower()
    keywords = {
        'match': ['match', 'rencontre', 'score', 'but', 'victoire', 'défaite', 'nul'],
        'transfert': ['transfert', 'mercato', 'signature', 'arrivée', 'départ', 'contrat'],
        'blessure': ['blessure', 'blessé', 'indisponible', 'absent'],
        'championnat': ['championnat', 'ligue 1', 'classement', 'champion'],
        'coupe': ['coupe', 'finale', 'trophée'],
        'entraineur': ['entraîneur', 'coach', 'staff'],
        'arbitrage': ['arbitre', 'carton', 'var', 'penalty'],
        'jeune': ['jeune', 'espoir', 'formation'],
        'contrat': ['prolongation', 'résiliation', 'accord'],
        'exclusif': ['exclu', 'exclusive', 'révélation', 'scoop'],
        'breaking': ['breaking', 'urgence', 'immédiat', 'flash']
    }
    scores = {cat: 0 for cat in keywords}
    for cat, words in keywords.items():
        for w in words:
            if w in text: scores[cat] += 1
    main_category = max(scores, key=scores.get)
    if scores[main_category] == 0:
        main_category = 'general'
    sub_categories = [cat for cat, score in scores.items() if score > 0][:3]
    return main_category, sub_categories

def generate_enriched_content(title, summary, source):
    main_cat, sub_cats = analyze_content(title, summary)
    clean_summary = clean_text(summary)
    clean_title = clean_text(title, max_len=80)
    accroche = random.choice(PHRASES_ACCROCHE.get(main_cat, PHRASES_ACCROCHE['general']))
    emojis = []
    for cat in [main_cat] + sub_cats[:2]:
        if cat in EMOJI_CATEGORIES:
            emojis.append(random.choice(EMOJI_CATEGORIES[cat]))
    emojis = list(dict.fromkeys(emojis)) or ['⚽','📰']
    if len(clean_summary) > 300:
        formatted_summary = f"{clean_summary[:200]}...\n\n💡 {clean_summary[-100:]}"
    else:
        formatted_summary = clean_summary
    hashtags = ' '.join(random.sample(HASHTAGS_FR, min(5, len(HASHTAGS_FR))))
    source_name = source or "Média"
    message = f"{''.join(emojis)} {accroche}*{clean_title}*\n\n{formatted_summary}\n\n📰 *Source :* {source_name}\n🕐 *Publié :* {datetime.now().strftime('%H:%M')}\n📊 *Catégorie :* {main_cat.upper()}\n\n{hashtags}"
    return escape_markdown(message)

# ---------------- POST NEWS ----------------
async def post_to_channels(photo_url, message, button_url=None):
    keyboard = None
    if button_url:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔘 Rejoindre le canal", url=button_url)]])
    for channel in CHANNELS:
        try:
            await bot.send_photo(chat_id=channel, photo=photo_url, caption=message, parse_mode="MarkdownV2", reply_markup=keyboard)
            logger.info(f"✅ Publié sur {channel}")
        except TelegramError as e:
            logger.error(f"❌ Telegram error {channel}: {e}")
        await asyncio.sleep(random.randint(5,10))

# ---------------- PROMO ----------------
PROMO_MESSAGE = "🚫 Arrêté d'acheter les C0UP0NS qui vont perdre tous le temps🚫, un bon pronostiqueur ne vend rien si effectivement il gagne✅, Venez prendre les C0UP0NS GRATUITEMENT✅ tout les jours dans ce CANAL TELEGRAM🌐 fiable à 90%\n\n🔵Lien du CANAL : https://t.me/mrxpronosfr"

async def send_promo():
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔘 Rejoindre le canal", url="https://t.me/mrxpronosfr")]])
    for channel in CHANNELS:
        try:
            await bot.send_message(chat_id=channel, text=escape_markdown(PROMO_MESSAGE), parse_mode="MarkdownV2", reply_markup=keyboard)
            logger.info(f"📢 Envoi message promotionnel à {channel}")
        except TelegramError as e:
            logger.error(f"❌ Erreur promo {channel}: {e}")

# ---------------- SCHEDULER ----------------
async def promo_scheduler():
    while True:
        await send_promo()  # Premier envoi
        await asyncio.sleep(12*60*60)  # 12h → 2x/jour

async def main():
    logger.info("🤖 Bot Football + Promo démarré")
    await promo_scheduler()  # Lancement du promo scheduler

if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNELS:
        logger.error("❌ BOT_TOKEN et CHANNELS requis")
        exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt propre")
