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
import hashlib

# 🔑 CONFIGURATION
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# 🔗 Flux RSS francophones exclusivement
RSS_FEEDS = [
    # Sport généralistes francophones
    "https://www.lequipe.fr/rss/actu_rss_Football.xml",
    "https://rmcsport.bfmtv.com/rss/football/",
    "https://www.eurosport.fr/football/rss.xml",
    
    # Médias français généralistes (rubrique football)
    "https://www.20minutes.fr/sport/football/rss",
    "https://www.leparisien.fr/sports/football/rss.xml",
    "https://www.lefigaro.fr/sports/football/rss.xml",
    
    # Médias sportifs spécialisés
    "https://www.footmercato.net/rss",
    "https://www.maxifoot.fr/rss.xml",
    "https://www.foot01.com/rss/football.xml",
    
    # Télévisions francophones
    "https://www.france24.com/fr/sports/football/rss",
    "https://www.tf1info.fr/football/rss.xml",
    "https://www.bfmtv.com/rss/sports/football/",
    
    # Presse régionale (bonne couverture football)
    "https://www.ouest-france.fr/sport/football/rss.xml",
    "https://www.lavoixdunord.fr/sports/football/rss",
    
    # Blogs spécialisés reconnus
    "https://www.cahiersdufootball.net/rss.xml",
]

POSTED_FILE = "posted.json"
MAX_POSTED_LINKS = 2500
IMAGE_CACHE = {}

# ⚙️ Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 🎨 Système d'emojis par type d'article
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
    'annonce': ["📢 ANNONCE : ", "🎊 RÉVÉLATION : ", "💎 SORTIE : "]
}

HASHTAGS_FR = [
    "#Foot", "#Football", "#Ligue1", "#LigueDesChampions", "#CoupeDeFrance",
    "#PSG", "#OM", "#OL", "#LOSC", "#ASM", "#SRFC", "#FRA", "#TeamFrance",
    "#Mercato", "#Transfert", "#BallonDor", "#UEFA", "#ChampionsLeague"
]

# Initialisation du bot
bot = Bot(token=BOT_TOKEN)

# 🔄 Chargement des liens postés
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

# 🖼️ Extraction robuste de l'image ORIGINALE
def extract_original_image(entry, feed_url):
    """Extrait l'image EXACTE de l'article original"""
    try:
        # 1. MEDIA_CONTENT (souvent l'image principale dans les flux modernes)
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image'):
                    url = media.get('url')
                    if url and is_valid_image_url(url):
                        logger.debug(f"✅ Image trouvée dans media_content: {url[:80]}...")
                        return url
        
        # 2. MEDIA_THUMBNAIL
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            for thumb in entry.media_thumbnail:
                url = thumb.get('url')
                if url and is_valid_image_url(url):
                    logger.debug(f"✅ Image trouvée dans media_thumbnail: {url[:80]}...")
                    return url
        
        # 3. ENCLOSURES (images jointes)
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image'):
                    url = enc.get('href')
                    if url and is_valid_image_url(url):
                        logger.debug(f"✅ Image trouvée dans enclosures: {url[:80]}...")
                        return url
        
        # 4. CONTENT:VALUE (contenu HTML complet)
        if hasattr(entry, 'content') and entry.content:
            for content in entry.content:
                if hasattr(content, 'value'):
                    soup = BeautifulSoup(content.value, 'html.parser')
                    # Chercher les images avec des classes significatives
                    img_selectors = [
                        'img[class*="principal"]', 'img[class*="featured"]',
                        'img[class*="hero"]', 'img[class*="cover"]',
                        'img[class*="main"]', 'img[class*="article"]',
                        'picture img', 'figure img'
                    ]
                    
                    for selector in img_selectors:
                        imgs = soup.select(selector)
                        for img in imgs:
                            src = extract_img_src(img)
                            if src and is_valid_image_url(src):
                                logger.debug(f"✅ Image trouvée dans content (selector): {src[:80]}...")
                                return src
        
        # 5. SUMMARY/DESCRIPTION (dernier recours)
        content_fields = ['summary', 'description']
        for field in content_fields:
            if hasattr(entry, field) and getattr(entry, field):
                soup = BeautifulSoup(getattr(entry, field), 'html.parser')
                # Priorité aux grandes images
                imgs = soup.find_all('img')
                for img in imgs:
                    src = extract_img_src(img)
                    if src and is_valid_image_url(src):
                        logger.debug(f"✅ Image trouvée dans {field}: {src[:80]}...")
                        return src
        
        # 6. Si toujours pas d'image, essayer de récupérer depuis la page
        if hasattr(entry, 'link') and entry.link:
            logger.debug(f"⚠️ Pas d'image dans RSS, tentative depuis page: {entry.link[:80]}...")
            return None  # On ne va pas scrapper pour rester simple
        
        logger.warning("❌ Aucune image trouvée dans l'article")
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction image: {e}")
        return None

def extract_img_src(img_tag):
    """Extrait la meilleure source d'une balise img"""
    src = None
    
    # Priorité aux attributs de source
    if img_tag.get('data-src'):  # Lazy loading
        src = img_tag['data-src']
    elif img_tag.get('srcset'):
        # Prendre la plus grande image du srcset
        srcset = img_tag['srcset'].split(',')
        largest = srcset[0].strip().split(' ')[0]
        src = largest
    elif img_tag.get('src'):
        src = img_tag['src']
    
    # Nettoyer l'URL
    if src:
        src = src.strip()
        # Convertir les URLs relatives
        if src.startswith('//'):
            src = 'https:' + src
        # Supprimer les paramètres de tracking
        src = re.sub(r'(\?|&)(utm_.*?|fbclid|gclid)=[^&]+', '', src)
        src = src.split('?')[0]  # Garder uniquement l'URL de base
    
    return src

def is_valid_image_url(url):
    """Vérifie si l'URL est une image valide"""
    if not url:
        return False
    
    # Vérifier l'extension
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    if not any(ext in url.lower() for ext in valid_extensions):
        return False
    
    # Vérifier que ce n'est pas un pixel tracker
    if any(pattern in url.lower() for pattern in ['pixel', 'tracker', '1x1.gif', 'spacer.gif']):
        return False
    
    # Vérifier la taille probable (éviter les miniatures)
    if any(pattern in url.lower() for pattern in ['thumb', 'mini', 'small', '_s.', '_m.']):
        # Vérifier s'il y a une version plus grande
        url_large = re.sub(r'(_s|_m|_thumb|_mini|_small)(\.\w+)$', r'\2', url)
        if url_large != url:
            return False
    
    return True

# 🎯 Analyse et catégorisation du contenu
def analyze_content(title, summary):
    """Analyse le contenu pour déterminer la catégorie"""
    text = f"{title} {summary}".lower()
    
    # Dictionnaire de mots-clés par catégorie
    keywords = {
        'match': ['match', 'rencontre', 'affrontement', 'score', 'but', 'résultat', 'victoire', 'défaite', 'nul'],
        'transfert': ['transfert', 'mercato', 'signature', 'recrutement', 'arrivée', 'départ', 'contrat'],
        'blessure': ['blessure', 'blessé', 'indisponible', 'absent', 'retour', 'rééducation'],
        'championnat': ['championnat', 'ligue 1', 'ligue 2', 'classement', 'champion', 'titré'],
        'coupe': ['coupe', 'élimination', 'quart', 'demi', 'finale', 'trophée'],
        'entraineur': ['entraîneur', 'coach', 'technicien', 'staff', 'remplacement'],
        'arbitrage': ['arbitre', 'arbitrage', 'carton', 'var', 'penalty', 'faute'],
        'jeune': ['jeune', 'espoir', 'promotion', 'formation', 'académie'],
        'contrat': ['prolongation', 'résiliation', 'accord', 'négociation', 'salaires'],
        'exclusif': ['exclu', 'exclusive', 'révélation', 'scoop', 'information'],
        'breaking': ['breaking', 'urgence', 'immédiat', 'dernière minute', 'flash']
    }
    
    # Compter les occurrences
    scores = {cat: 0 for cat in keywords}
    for category, words in keywords.items():
        for word in words:
            if word in text:
                scores[category] += 1
    
    # Déterminer la catégorie principale
    main_category = max(scores, key=scores.get)
    if scores[main_category] == 0:
        main_category = 'general'
    
    # Sous-catégories (pour emojis diversifiés)
    sub_categories = [cat for cat, score in scores.items() if score > 0][:3]
    
    return main_category, sub_categories

# ✨ Génération du contenu enrichi
def generate_enriched_content(title, summary, source):
    """Génère un contenu enrichi sans IA"""
    # Analyser le contenu
    main_cat, sub_cats = analyze_content(title, summary)
    
    # Nettoyer le texte
    clean_summary = clean_text(summary)
    clean_title = clean_text(title, max_len=80)
    
    # Choisir l'accroche adaptée
    if main_cat in PHRASES_ACCROCHE:
        accroche = random.choice(PHRASES_ACCROCHE[main_cat])
    else:
        accroche = random.choice(PHRASES_ACCROCHE['general'])
    
    # Sélectionner les emojis
    emojis = []
    for cat in [main_cat] + sub_cats[:2]:
        if cat in EMOJI_CATEGORIES:
            emojis.append(random.choice(EMOJI_CATEGORIES[cat]))
    
    # Éviter les doublons
    emojis = list(dict.fromkeys(emojis))
    if not emojis:
        emojis = ['⚽', '📰']
    
    # Générer le texte enrichi
    if len(clean_summary) > 300:
        # Prendre le début et la fin
        first_part = clean_summary[:200]
        last_part = clean_summary[-100:]
        formatted_summary = f"{first_part}...\n\n💡 {last_part}"
    else:
        formatted_summary = clean_summary
    
    # Sélectionner les hashtags pertinents
    relevant_hashtags = []
    for cat in [main_cat] + sub_cats:
        hashtag_map = {
            'match': ['#Match', '#Ligue1'],
            'transfert': ['#Mercato', '#Transfert'],
            'psg': ['#PSG'],
            'om': ['#OM'],
            'ol': ['#OL'],
            'france': ['#TeamFrance', '#FRA']
        }
        if cat in hashtag_map:
            relevant_hashtags.extend(hashtag_map[cat])
    
    # Ajouter des hashtags généraux
    relevant_hashtags.extend(random.sample(HASHTAGS_FR, min(3, len(HASHTAGS_FR))))
    relevant_hashtags = list(dict.fromkeys(relevant_hashtags))[:5]
    
    # Formater la source
    source_name = source if source else "Média"
    if "lequipe" in source_name.lower():
        source_name = "L'Équipe"
    elif "rmc" in source_name.lower():
        source_name = "RMC Sport"
    
    # Construire le message final
    message = f"""{''.join(emojis)} {accroche}*{clean_title}*

{formatted_summary}

📰 *Source :* {source_name}
🕐 *Publié :* {datetime.now().strftime('%H:%M')}
📊 *Catégorie :* {main_cat.upper()}

{' '.join(relevant_hashtags)}"""
    
    return message

def clean_text(text, max_len=500):
    """Nettoie le texte pour Telegram"""
    if not text:
        return ""
    
    # Supprimer le HTML
    text = re.sub(r'<[^>]+>', '', text)
    # Supprimer les URLs
    text = re.sub(r'https?://\S+', '', text)
    # Supprimer les caractères bizarres
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    # Normaliser les espaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Tronquer si nécessaire
    if len(text) > max_len:
        text = text[:max_len] + "..."
    
    return text

# 📰 Fonction principale de publication
async def check_and_post_news():
    """Vérifie et publie les nouvelles"""
    logger.info("🔍 Scan des flux français...")
    new_posts = 0
    
    # Session HTTP pour les vérifications
    async with aiohttp.ClientSession() as session:
        for feed_url in RSS_FEEDS:
            try:
                logger.info(f"📡 Lecture: {feed_url}")
                
                # Parser le flux
                feed = feedparser.parse(feed_url)
                
                # Vérifier la langue
                if hasattr(feed, 'language') and feed.language not in ['fr', 'fr-FR', 'fr-fr']:
                    logger.warning(f"⚠️ Flux non-français ignoré: {feed.language}")
                    continue
                
                if feed.bozo:
                    logger.warning(f"⚠️ Erreur flux: {feed.bozo_exception}")
                    continue
                
                if not feed.entries:
                    logger.warning(f"⚠️ Flux vide")
                    continue
                
                # Traiter les 3 derniers articles
                for entry in feed.entries[:3]:
                    try:
                        # Vérifications essentielles
                        if not hasattr(entry, 'link') or not entry.link:
                            continue
                        
                        link = entry.link.strip()
                        
                        # Vérifier si déjà posté
                        if link in posted_links:
                            continue
                        
                        # Extraire l'image ORIGINALE
                        image_url = extract_original_image(entry, feed_url)
                        
                        if not image_url:
                            logger.warning(f"⚠️ Pas d'image pour: {entry.get('title', 'Sans titre')[:50]}...")
                            continue
                        
                        # Récupérer le titre
                        title = entry.title if hasattr(entry, 'title') else "Actualité Football"
                        
                        # Récupérer le contenu
                        content = ""
                        if hasattr(entry, 'summary'):
                            content = entry.summary
                        elif hasattr(entry, 'description'):
                            content = entry.description
                        else:
                            content = title
                        
                        # Source
                        source = ""
                        if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                            source = entry.source.title
                        elif hasattr(feed, 'title'):
                            source = feed.title
                        
                        # Générer le contenu enrichi
                        message = generate_enriched_content(title, content, source)
                        
                        # Vérifier que l'image est accessible
                        try:
                            async with session.get(image_url, timeout=5) as resp:
                                if resp.status != 200:
                                    logger.warning(f"⚠️ Image inaccessible: {image_url[:80]}...")
                                    continue
                        except:
                            logger.warning(f"⚠️ Timeout image: {image_url[:80]}...")
                            continue
                        
                        # Publier sur Telegram
                        logger.info(f"📤 Publication: {title[:60]}...")
                        
                        await bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=image_url,
                            caption=message,
                            parse_mode="Markdown"
                        )
                        
                        # Mettre à jour
                        posted_links.add(link)
                        new_posts += 1
                        
                        # Attente anti-spam
                        wait_time = random.randint(10, 20)
                        logger.debug(f"⏳ Attente de {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        
                    except TelegramError as e:
                        logger.error(f"❌ Erreur Telegram: {e}")
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.error(f"❌ Erreur article: {e}")
                        continue
                    
            except Exception as e:
                logger.error(f"❌ Erreur flux: {e}")
                continue
    
    # Sauvegarder si nouveautés
    if new_posts > 0:
        save_posted_links()
        logger.info(f"✅ {new_posts} article(s) publié(s)")
    else:
        logger.info("⏱️ Aucune nouvelle actualité")
    
    return new_posts

# 🔁 Scheduler
async def main_scheduler():
    """Boucle principale"""
    logger.info("🤖 Bot Football Français")
    logger.info("📰 Sources exclusivement francophones")
    logger.info(f"📊 {len(RSS_FEEDS)} flux surveillés")
    logger.info(f"📁 {len(posted_links)} articles en mémoire")
    
    # Premier check
    await check_and_post_news()
    
    # Intervalle adaptatif
    base_interval = 420  # 7 minutes
    
    while True:
        try:
            start_time = datetime.now()
            
            new_posts = await check_and_post_news()
            
            # Ajuster l'intervalle selon l'activité
            if new_posts > 2:
                interval = base_interval * 2  # Plus long si beaucoup de posts
            elif new_posts > 0:
                interval = base_interval
            else:
                interval = base_interval // 2  # Plus court si rien
            
            elapsed = (datetime.now() - start_time).seconds
            wait_time = max(interval - elapsed, 60)
            
            next_check = datetime.now().timestamp() + wait_time
            next_str = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
            
            logger.info(f"⏰ Prochain scan à {next_str} ({wait_time//60}min)")
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
    # Validation
    if not BOT_TOKEN or not CHANNEL_ID:
        logger.error("❌ BOT_TOKEN et CHANNEL_ID requis")
        exit(1)
    
    logger.info("🚀 Démarrage du bot...")
    
    try:
        asyncio.run(main_scheduler())
    except KeyboardInterrupt:
        logger.info("👋 Arrêt propre")
        save_posted_links()
    except Exception as e:
        logger.error(f"💥 Crash: {e}")
        exit(1)