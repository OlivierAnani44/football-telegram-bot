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

# 🔗 Flux RSS 100% FRANÇAIS
RSS_FEEDS = [
    # L'Équipe (images haute qualité)
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    
    # RMC Sport (images directes)
    "https://rmcsport.bfmtv.com/rss/football/",
    
    # Le Parisien (bonnes images)
    "https://www.leparisien.fr/sports/football/rss.xml",
    
    # 20 Minutes (images média)
    "https://www.20minutes.fr/sport/football/rss",
    
    # Foot Mercato (transferts + images)
    "https://www.footmercato.net/rss",
    
    # Maxifoot (images détaillées)
    "https://www.maxifoot.fr/rss.xml",
    
    # France TV Sport
    "https://www.france.tv/france-2/stade-2/rss.xml",
    
    # Ouest-France (bonne qualité)
    "https://www.ouest-france.fr/sport/football/rss.xml",
    
    # La Dépêche
    "https://www.ladepeche.fr/sport/football/rss.xml",
    
    # RTL Sport
    "https://www.rtl.fr/sport/football/rss",
    
    # So Foot (analyse + images)
    "https://www.sofoot.com/rss.xml"
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 1500

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

# 🖼️ EXTRACTION D'IMAGE ROBUSTE - Identique à la publication
def extract_identical_image(entry, feed_url):
    """Extrait l'image EXACTE publiée avec l'article"""
    try:
        # 1. MEDIA_CONTENT - L'image principale du flux
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                media_type = media.get('type', '')
                media_url = media.get('url', '')
                
                if media_type.startswith('image') and media_url:
                    # Vérifier que c'est une vraie image (pas une miniature)
                    if not is_thumbnail(media_url):
                        logger.info(f"🖼️ Image trouvée dans media_content: {media_url[:100]}...")
                        return clean_image_url(media_url)
        
        # 2. ENCLOSURES - Images jointes au flux
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                enc_type = enc.get('type', '')
                enc_url = enc.get('href', '') or enc.get('url', '')
                
                if enc_type.startswith('image') and enc_url:
                    logger.info(f"🖼️ Image trouvée dans enclosures: {enc_url[:100]}...")
                    return clean_image_url(enc_url)
        
        # 3. MEDIA_THUMBNAIL (souvent la vraie image dans flux modernes)
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            # Prendre la plus grande image disponible
            thumbnails = []
            for thumb in entry.media_thumbnail:
                thumb_url = thumb.get('url', '')
                if thumb_url:
                    thumbnails.append(thumb_url)
            
            if thumbnails:
                # Prendre la dernière (souvent la plus grande)
                selected = thumbnails[-1]
                logger.info(f"🖼️ Image trouvée dans media_thumbnail: {selected[:100]}...")
                return clean_image_url(selected)
        
        # 4. CONTENT:VALUE - Extraire depuis le HTML complet
        if hasattr(entry, 'content') and entry.content:
            for content_item in entry.content:
                if hasattr(content_item, 'value'):
                    html_content = content_item.value
                    image_url = extract_image_from_html(html_content, feed_url)
                    if image_url:
                        logger.info(f"🖼️ Image extraite du HTML content: {image_url[:100]}...")
                        return image_url
        
        # 5. SUMMARY/DESCRIPTION - Dernier recours dans le HTML
        content_fields = ['summary', 'description']
        for field in content_fields:
            if hasattr(entry, field):
                field_content = getattr(entry, field)
                if field_content:
                    image_url = extract_image_from_html(str(field_content), feed_url)
                    if image_url:
                        logger.info(f"🖼️ Image extraite du {field}: {image_url[:100]}...")
                        return image_url
        
        logger.warning(f"⚠️ Aucune image trouvée pour l'article")
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction image: {e}")
        return None

def extract_image_from_html(html_content, base_url):
    """Extrait la meilleure image du HTML"""
    if not html_content:
        return None
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Chercher dans cet ordre de priorité :
        # 1. Images avec classes spécifiques (image principale)
        img_selectors = [
            'img.media', 'img.article-image', 'img.main-image',
            'img.featured', 'img.wp-post-image', 'img.attachment-full',
            'img[data-src*="large"]', 'img[src*="large"]',
            'picture img', 'figure img'
        ]
        
        for selector in img_selectors:
            imgs = soup.select(selector)
            for img in imgs:
                img_url = get_best_image_src(img)
                if img_url:
                    full_url = make_absolute_url(img_url, base_url)
                    if full_url and is_valid_image(full_url):
                        return full_url
        
        # 2. Toutes les images, triées par taille probable
        all_imgs = soup.find_all('img')
        valid_images = []
        
        for img in all_imgs:
            img_url = get_best_image_src(img)
            if img_url:
                full_url = make_absolute_url(img_url, base_url)
                if full_url and is_valid_image(full_url):
                    # Prioriser les grandes images
                    width = img.get('width', '0')
                    height = img.get('height', '0')
                    
                    # Estimer la taille
                    size_score = 0
                    try:
                        if width and height:
                            size_score = int(width) * int(height)
                    except:
                        pass
                    
                    valid_images.append((full_url, size_score))
        
        # Trier par taille et prendre la plus grande
        if valid_images:
            valid_images.sort(key=lambda x: x[1], reverse=True)
            return valid_images[0][0]
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction HTML: {e}")
        return None

def get_best_image_src(img_tag):
    """Retourne la meilleure source d'image depuis une balise img"""
    # Priorité : data-src (lazy loading), puis srcset, puis src
    if img_tag.get('data-src'):
        return img_tag['data-src']
    
    if img_tag.get('srcset'):
        # Prendre la plus grande image du srcset
        srcset_parts = img_tag['srcset'].split(',')
        largest = None
        largest_size = 0
        
        for part in srcset_parts:
            part = part.strip()
            if ' ' in part:
                url, size = part.rsplit(' ', 1)
                try:
                    if size.endswith('w'):
                        size_num = int(size[:-1])
                        if size_num > largest_size:
                            largest_size = size_num
                            largest = url
                except:
                    pass
        
        if largest:
            return largest
    
    if img_tag.get('src'):
        return img_tag['src']
    
    return None

def make_absolute_url(img_url, base_url):
    """Convertit une URL relative en absolue"""
    if not img_url:
        return None
    
    # Si déjà absolue
    if img_url.startswith(('http://', 'https://')):
        return img_url
    
    # Si commence par //
    if img_url.startswith('//'):
        return 'https:' + img_url
    
    # Si relative, construire l'URL complète
    try:
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        
        if img_url.startswith('/'):
            return base_domain + img_url
        else:
            return base_domain + '/' + img_url
            
    except:
        return None

def clean_image_url(url):
    """Nettoie l'URL de l'image"""
    if not url:
        return None
    
    # Supprimer les paramètres de tracking et redimensionnement
    url = re.sub(r'(\?|&)(w=\d+|h=\d+|resize=\d+|width=\d+|height=\d+)', '', url)
    url = re.sub(r'(\?|&)(quality=\d+|compress=\d+)', '', url)
    url = re.sub(r'(\?|&)(fit=\w+|crop=\w+)', '', url)
    
    # Supprimer les trackers
    url = re.sub(r'(\?|&)(utm_.*?|fbclid|gclid|dclid)=[^&]+', '', url)
    
    # Garder uniquement avant le ?
    if '?' in url:
        url = url.split('?')[0]
    
    return url

def is_thumbnail(url):
    """Détecte si c'est une miniature"""
    if not url:
        return True
    
    url_lower = url.lower()
    thumbnail_indicators = [
        'thumb', 'thumbnail', 'mini', 'small', '_s.', '_m.', '_t.',
        'w=100', 'h=100', 'size=100', '100x100', '150x150'
    ]
    
    return any(indicator in url_lower for indicator in thumbnail_indicators)

def is_valid_image(url):
    """Vérifie si l'URL pointe vers une image valide"""
    if not url:
        return False
    
    # Vérifier l'extension
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    if not any(url.lower().endswith(ext) for ext in valid_extensions):
        # Vérifier si c'est une URL d'API d'image
        if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png']):
            return True
        return False
    
    # Vérifier que ce n'est pas un tracker
    if any(pattern in url.lower() for pattern in ['pixel', 'tracker', '1x1.gif', 'spacer.gif', 'blank.gif']):
        return False
    
    # Vérifier la taille minimale (éviter les icônes)
    if any(pattern in url.lower() for pattern in ['icon', 'logo', 'favicon']):
        return False
    
    return True

# 🇫🇷 Vérification du contenu français
def is_french_content(text):
    """Vérifie si le texte est en français"""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Mots français courants dans le football
    french_indicators = [
        'football', 'match', 'équipe', 'joueur', 'but', 'victoire', 
        'défaite', 'championnat', 'coupe', 'ligue', 'entraîneur',
        'stade', 'public', 'arbitre', 'carton', 'penalty', 'transfert',
        'mercato', 'contrat', 'blessure', 'composition', 'remplacement'
    ]
    
    french_count = sum(1 for word in french_indicators if word in text_lower)
    
    # Si plusieurs mots français sont présents
    return french_count >= 3

def clean_french_text(text, max_len=400):
    """Nettoie le texte français"""
    if not text:
        return ""
    
    # Supprimer HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Supprimer URLs
    text = re.sub(r'https?://\S+', '', text)
    # Supprimer entités HTML
    text = re.sub(r'&[a-z]+;', ' ', text)
    # Normaliser espaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Tronquer intelligemment
    if len(text) > max_len:
        # Chercher un point de coupure naturel
        last_period = text[:max_len].rfind('. ')
        last_excl = text[:max_len].rfind('! ')
        
        cutoff = max(last_period, last_excl)
        if cutoff > max_len // 2:
            text = text[:cutoff + 1]
        else:
            text = text[:max_len] + "..."
    
    return text

# 📰 Fonction principale
async def check_and_post_news():
    """Vérifie et poste les actualités françaises"""
    logger.info("🔍 Recherche d'actualités football...")
    new_posts = 0
    
    # Session HTTP pour vérifier les images
    async with aiohttp.ClientSession() as session:
        for feed_url in RSS_FEEDS:
            try:
                logger.info(f"📡 Lecture flux: {feed_url}")
                
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    logger.warning(f"⚠️ Erreur flux: {feed.bozo_exception}")
                    continue
                
                if not feed.entries:
                    logger.warning(f"⚠️ Flux vide")
                    continue
                
                # Traiter 3 derniers articles
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
                        
                        # Extraire l'image IDENTIQUE
                        image_url = extract_identical_image(entry, feed_url)
                        
                        if not image_url:
                            logger.warning(f"⚠️ Pas d'image pour: {title[:50]}...")
                            continue
                        
                        # Vérifier que l'image est accessible
                        try:
                            async with session.get(image_url, timeout=10) as resp:
                                if resp.status != 200:
                                    logger.warning(f"⚠️ Image inaccessible: {image_url[:80]}...")
                                    continue
                                
                                # Vérifier le content-type
                                content_type = resp.headers.get('Content-Type', '')
                                if not content_type.startswith('image/'):
                                    logger.warning(f"⚠️ Pas une image: {content_type}")
                                    continue
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur vérification image: {e}")
                            continue
                        
                        # Préparer le contenu
                        content = ""
                        if hasattr(entry, 'summary'):
                            content = entry.summary
                        elif hasattr(entry, 'description'):
                            content = entry.description
                        
                        clean_title = clean_french_text(title, 80)
                        clean_content = clean_french_text(content, 350)
                        
                        # Source
                        source = ""
                        if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                            source = entry.source.title
                        elif hasattr(feed.feed, 'title'):
                            source = feed.feed.title
                        
                        # Hashtags selon le contenu
                        hashtags = ["#Football", "#ActuFoot", "#Sports"]
                        if 'psg' in clean_title.lower() or 'paris' in clean_title.lower():
                            hashtags.append("#PSG")
                        if 'marseille' in clean_title.lower() or 'om' in clean_title.lower():
                            hashtags.append("#OM")
                        if 'lyon' in clean_title.lower() or 'ol' in clean_title.lower():
                            hashtags.append("#OL")
                        if 'transfert' in clean_title.lower() or 'mercato' in clean_title.lower():
                            hashtags.append("#Mercato")
                        
                        # Construire le message
                        message = f"""⚽ *ACTUALITÉ FOOTBALL*

*{clean_title}*

{clean_content}

📰 Source: {source[:30]}
🕐 {datetime.now().strftime('%H:%M')}

{' '.join(hashtags)}"""
                        
                        # Publier
                        logger.info(f"📤 Publication: {clean_title[:50]}...")
                        logger.info(f"🖼️ Image: {image_url[:80]}...")
                        
                        await bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=image_url,
                            caption=message,
                            parse_mode="Markdown"
                        )
                        
                        posted_links.add(link)
                        new_posts += 1
                        
                        # Attente
                        await asyncio.sleep(random.randint(8, 12))
                        
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
        logger.info(f"✅ {new_posts} article(s) publié(s) avec images originales")
    else:
        logger.info("⏱️ Aucune nouvelle actualité")
    
    return new_posts

# 🔁 Scheduler
async def main_scheduler():
    """Boucle principale"""
    logger.info("🤖 Bot Football Français")
    logger.info("🖼️ Images identiques aux publications")
    logger.info(f"📊 {len(RSS_FEEDS)} flux surveillés")
    
    await check_and_post_news()
    
    interval = 300  # 5 minutes
    
    while True:
        try:
            start_time = datetime.now()
            
            new_posts = await check_and_post_news()
            
            elapsed = (datetime.now() - start_time).seconds
            wait_time = max(interval - elapsed, 60)
            
            next_check = datetime.now().timestamp() + wait_time
            next_time = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
            
            logger.info(f"⏰ Prochain scan à {next_time}")
            logger.info("-" * 50)
            
            await asyncio.sleep(wait_time)
            
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé")
            save_posted_links()
            break
        except Exception as e:
            logger.error(f"🚨 Erreur: {e}")
            await asyncio.sleep(60)

# 🏁 Lancement
if __name__ == "__main__":
    if not BOT_TOKEN or not CHANNEL_ID:
        logger.error("❌ Variables manquantes")
        exit(1)
    
    try:
        asyncio.run(main_scheduler())
    except KeyboardInterrupt:
        logger.info("👋 Arrêt")
        save_posted_links()
    except Exception as e:
        logger.error(f"💥 Erreur: {e}")