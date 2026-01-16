import os
import feedparser
import json
import asyncio
import logging
import re
from telegram import Bot
from telegram.error import TelegramError
from bs4 import BeautifulSoup
import random
from datetime import datetime
import aiohttp
from urllib.parse import urlparse, urljoin

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# 🔗 LES 3 FLUX RSS FRANÇAIS
RSS_FEEDS = [
    "https://www.footmercato.net/rss",          # Transferts et actualités
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",  # L'Équipe - référence
    "https://rmcsport.bfmtv.com/rss/football/"  # RMC Sport - infos en continu
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 1000

# ⚙️ Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialisation du bot
bot = Bot(token=BOT_TOKEN)

# 🔄 Chargement des liens postés
def load_posted_links():
    try:
        if os.path.exists(POSTED_FILE):
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                links = set(json.load(f))
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

# 🖼️ EXTRACTION D'IMAGE SPÉCIFIQUE POUR CHAQUE FLUX
def extract_image_for_feed(entry, feed_url):
    """Extrait l'image selon le flux RSS"""
    
    # Pour L'Équipe
    if "lequipe.fr" in feed_url:
        return extract_lequipe_image(entry)
    
    # Pour RMC Sport
    elif "rmcsport.bfmtv.com" in feed_url:
        return extract_rmc_image(entry)
    
    # Pour Foot Mercato
    elif "footmercato.net" in feed_url:
        return extract_footmercato_image(entry)
    
    # Fallback général
    else:
        return extract_general_image(entry, feed_url)

def extract_lequipe_image(entry):
    """Extrait l'image de L'Équipe"""
    try:
        # L'Équipe met l'image dans media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image'):
                    img_url = media.get('url', '')
                    if img_url:
                        # Nettoyer l'URL L'Équipe
                        img_url = re.sub(r'(\?.*$)', '', img_url)
                        logger.info(f"🖼️ L'Équipe - Image media_content: {img_url[:80]}...")
                        return img_url
        
        # Fallback pour L'Équipe
        if hasattr(entry, 'summary'):
            return extract_image_from_html(entry.summary, "https://www.lequipe.fr")
        
        return None
    except Exception as e:
        logger.error(f"❌ Erreur L'Équipe image: {e}")
        return None

def extract_rmc_image(entry):
    """Extrait l'image de RMC Sport"""
    try:
        # RMC utilise enclosures
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    img_url = enc.get('href', '') or enc.get('url', '')
                    if img_url:
                        logger.info(f"🖼️ RMC - Image enclosures: {img_url[:80]}...")
                        return img_url
        
        # RMC aussi dans media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image'):
                    img_url = media.get('url', '')
                    if img_url:
                        logger.info(f"🖼️ RMC - Image media_content: {img_url[:80]}...")
                        return img_url
        
        # Fallback HTML
        if hasattr(entry, 'summary'):
            return extract_image_from_html(entry.summary, "https://rmcsport.bfmtv.com")
        
        return None
    except Exception as e:
        logger.error(f"❌ Erreur RMC image: {e}")
        return None

def extract_footmercato_image(entry):
    """Extrait l'image de Foot Mercato"""
    try:
        # Foot Mercato utilise media:content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image'):
                    img_url = media.get('url', '')
                    if img_url:
                        logger.info(f"🖼️ Foot Mercato - Image media_content: {img_url[:80]}...")
                        return img_url
        
        # Dans summary avec balise img
        if hasattr(entry, 'summary'):
            soup = BeautifulSoup(entry.summary, 'html.parser')
            img = soup.find('img')
            if img:
                src = img.get('src') or img.get('data-src')
                if src:
                    # Convertir URL relative
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = 'https://www.footmercato.net' + src
                    
                    logger.info(f"🖼️ Foot Mercato - Image HTML: {src[:80]}...")
                    return src
        
        # Fallback description
        if hasattr(entry, 'description'):
            return extract_image_from_html(entry.description, "https://www.footmercato.net")
        
        return None
    except Exception as e:
        logger.error(f"❌ Erreur Foot Mercato image: {e}")
        return None

def extract_general_image(entry, feed_url):
    """Extrait l'image pour les flux généraux"""
    try:
        # Essayer media_content d'abord
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image'):
                    img_url = media.get('url', '')
                    if img_url:
                        return img_url
        
        # Enclosures ensuite
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    img_url = enc.get('href', '') or enc.get('url', '')
                    if img_url:
                        return img_url
        
        # HTML en dernier
        if hasattr(entry, 'summary'):
            return extract_image_from_html(entry.summary, feed_url)
        
        return None
    except Exception as e:
        logger.error(f"❌ Erreur général image: {e}")
        return None

def extract_image_from_html(html_content, base_url):
    """Extrait l'image depuis le HTML"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        img = soup.find('img')
        
        if img:
            src = img.get('src') or img.get('data-src')
            if src:
                # Convertir URL relative en absolue
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    parsed = urlparse(base_url)
                    src = f"{parsed.scheme}://{parsed.netloc}{src}"
                elif not src.startswith('http'):
                    src = urljoin(base_url, src)
                
                return src
    except Exception as e:
        logger.error(f"❌ Erreur extraction HTML: {e}")
    
    return None

# 🇫🇷 Vérification du contenu français
def is_french_content(text):
    """Vérifie rapidement si le texte est en français"""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Mots clés français courants dans le football
    french_words = [
        'le ', 'la ', 'les ', 'un ', 'une ', 'des ', 'du ', 'de ',
        'à ', 'au ', 'aux ', 'et ', 'ou ', 'dans ', 'sur ', 'avec ',
        'football', 'match', 'équipe', 'joueur', 'but', 'victoire',
        'défaite', 'championnat', 'coupe', 'ligue', 'entraîneur'
    ]
    
    french_count = sum(1 for word in french_words if word in text_lower)
    
    # Si au moins 3 mots français sont présents
    return french_count >= 3

def clean_french_text(text, max_len=400):
    """Nettoie le texte français"""
    if not text:
        return ""
    
    # Supprimer HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Supprimer URLs
    text = re.sub(r'https?://\S+', '', text)
    # Supprimer caractères spéciaux
    text = re.sub(r'[^\w\s.,!?;:\'-]', ' ', text)
    # Normaliser espaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Tronquer si trop long
    if len(text) > max_len:
        # Chercher un point de coupure naturel
        last_period = text[:max_len].rfind('. ')
        if last_period > max_len // 2:
            text = text[:last_period + 1]
        else:
            text = text[:max_len] + "..."
    
    return text

def get_source_name(feed_url):
    """Retourne le nom du média"""
    if "lequipe.fr" in feed_url:
        return "L'Équipe"
    elif "rmcsport.bfmtv.com" in feed_url:
        return "RMC Sport"
    elif "footmercato.net" in feed_url:
        return "Foot Mercato"
    else:
        return "Source"

# 📰 Fonction principale
async def check_and_post_news():
    """Vérifie et poste les actualités"""
    logger.info("🔍 Scan des 3 flux français...")
    new_posts = 0
    
    # Session pour vérifier les images
    async with aiohttp.ClientSession() as session:
        for feed_url in RSS_FEEDS:
            try:
                logger.info(f"📡 Lecture: {get_source_name(feed_url)}")
                
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    logger.warning(f"⚠️ Erreur flux {feed_url}: {feed.bozo_exception}")
                    continue
                
                if not feed.entries:
                    logger.warning(f"⚠️ Flux vide")
                    continue
                
                # Prendre les 3 derniers articles
                for entry in feed.entries[:3]:
                    try:
                        # Vérifications de base
                        if not hasattr(entry, 'link') or not entry.link:
                            continue
                        
                        link = entry.link.strip()
                        
                        if link in posted_links:
                            continue
                        
                        if not hasattr(entry, 'title') or not entry.title:
                            continue
                        
                        title = entry.title
                        
                        # Vérifier que c'est en français
                        if not is_french_content(title):
                            logger.warning(f"⚠️ Contenu non-français ignoré: {title[:50]}...")
                            continue
                        
                        # Extraire l'image spécifique au flux
                        image_url = extract_image_for_feed(entry, feed_url)
                        
                        if not image_url:
                            logger.warning(f"⚠️ Pas d'image pour: {title[:50]}...")
                            continue
                        
                        # Vérifier que l'image est accessible
                        try:
                            async with session.get(image_url, timeout=10) as resp:
                                if resp.status != 200:
                                    logger.warning(f"⚠️ Image inaccessible: {image_url[:80]}...")
                                    continue
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur image: {e}")
                            continue
                        
                        # Préparer le contenu
                        content = ""
                        if hasattr(entry, 'summary'):
                            content = entry.summary
                        elif hasattr(entry, 'description'):
                            content = entry.description
                        else:
                            content = title
                        
                        clean_title = clean_french_text(title, 80)
                        clean_content = clean_french_text(content, 350)
                        
                        # Source et hashtags
                        source = get_source_name(feed_url)
                        
                        # Hashtags adaptés
                        hashtags = ["#Football", "#ActuFoot"]
                        title_lower = clean_title.lower()
                        
                        if 'psg' in title_lower or 'paris' in title_lower:
                            hashtags.append("#PSG")
                        if 'marseille' in title_lower or 'om' in title_lower:
                            hashtags.append("#OM")
                        if 'lyon' in title_lower or 'ol' in title_lower:
                            hashtags.append("#OL")
                        if 'transfert' in title_lower or 'mercato' in title_lower:
                            hashtags.append("#Mercato")
                        if 'france' in title_lower or 'bleus' in title_lower:
                            hashtags.append("#TeamFrance")
                        
                        # Message formaté
                        message = f"""⚽ *ACTUALITÉ FOOTBALL*

*{clean_title}*

{clean_content}

📰 *Source :* {source}
🕐 *Publié :* {datetime.now().strftime('%H:%M')}

{' '.join(hashtags)}"""
                        
                        # Publier
                        logger.info(f"📤 Publication depuis {source}: {clean_title[:50]}...")
                        
                        await bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=image_url,
                            caption=message,
                            parse_mode="Markdown"
                        )
                        
                        posted_links.add(link)
                        new_posts += 1
                        
                        # Attente entre posts
                        await asyncio.sleep(10)
                        
                    except TelegramError as e:
                        logger.error(f"❌ Erreur Telegram: {e}")
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(f"❌ Erreur article: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Erreur flux: {e}")
                continue
    
    # Sauvegarder
    if new_posts > 0:
        save_posted_links()
        logger.info(f"✅ {new_posts} nouvel(le)s publication(s)")
    else:
        logger.info("⏱️ Aucun nouvel article")
    
    return new_posts

# 🔁 Scheduler
async def main_scheduler():
    """Boucle principale"""
    logger.info("🤖 Bot Football Français")
    logger.info("🎯 3 flux sélectionnés:")
    logger.info("   📰 Foot Mercato")
    logger.info("   📰 L'Équipe")
    logger.info("   📰 RMC Sport")
    logger.info(f"📁 {len(posted_links)} articles déjà postés")
    
    # Premier scan
    await check_and_post_news()
    
    # Intervalle : 4 minutes
    interval = 240
    
    while True:
        try:
            await check_and_post_news()
            
            # Prochain check
            next_time = datetime.now().timestamp() + interval
            next_str = datetime.fromtimestamp(next_time).strftime('%H:%M:%S')
            
            logger.info(f"⏰ Prochain scan à {next_str}")
            logger.info("-" * 40)
            
            await asyncio.sleep(interval)
            
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé")
            save_posted_links()
            break
        except Exception as e:
            logger.error(f"🚨 Erreur: {e}")
            await asyncio.sleep(60)

# 🏁 Lancement
if __name__ == "__main__":
    # Vérification des variables
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN manquant")
        exit(1)
    
    if not CHANNEL_ID:
        logger.error("❌ CHANNEL_ID manquant")
        exit(1)
    
    logger.info("🚀 Démarrage du bot...")
    
    try:
        asyncio.run(main_scheduler())
    except KeyboardInterrupt:
        logger.info("👋 Arrêt propre")
        save_posted_links()
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")