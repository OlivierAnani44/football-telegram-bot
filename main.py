POSTED_FILE = "posted.json"
print("POSTED_FILE =", POSTED_FILE)
import os
import json
import logging
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait

# ---------------- CONFIG ----------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")
CHANNELS_RAW = os.getenv("CHANNELS")

# Configuration supplémentaire
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # Intervalle de vérification en secondes
MAX_MESSAGES_PER_CHECK = int(os.getenv("MAX_MESSAGES_PER_CHECK", "50"))  # Messages à vérifier par scan
FILTER_KEYWORDS = os.getenv("FILTER_KEYWORDS", "").lower().split(",")  # Mots-clés à filtrer

if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, CHANNELS_RAW]):
    raise RuntimeError("❌ Variables d'environnement manquantes")

API_ID = int(API_ID)

# SOURCE CHANNEL
if SOURCE_CHANNEL.startswith("@"):
    SOURCE_CHANNEL_USERNAME = SOURCE_CHANNEL
    SOURCE_CHANNEL_ID = None
else:
    SOURCE_CHANNEL_ID = int(SOURCE_CHANNEL)
    SOURCE_CHANNEL_USERNAME = None

# DESTINATION CHANNELS
CHANNELS = []
for c in CHANNELS_RAW.split(","):
    c = c.strip()
    if not c:
        continue
    if c.startswith("@"):
        CHANNELS.append(c)
    else:
        CHANNELS.append(int(c))

# ---------------- LOG ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------- POSTED ----------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Vérifier si c'est une liste ou un dict
                if isinstance(data, dict):
                    return set(data.get("posted_ids", []))
                return set(data)
        except Exception as e:
            logger.error(f"❌ Erreur lecture {POSTED_FILE}: {e}")
            return set()
    return set()

def save_posted():
    try:
        # Sauvegarder avec structure améliorée
        data = {
            "posted_ids": list(posted),
            "last_check": time.time(),
            "total_messages": len(posted)
        }
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde {POSTED_FILE}: {e}")

posted = load_posted()
logger.info(f"📊 {len(posted)} messages déjà traités")

# ---------------- FONCTIONS UTILITAIRES ----------------
def should_filter_message(text):
    """Vérifie si le message doit être filtré"""
    if not text:
        return False
    
    text_low = text.lower()
    
    # Filtres de base
    if "http" in text_low or "aten10" in text_low:
        return True
    
    # Filtres par mots-clés personnalisés
    if FILTER_KEYWORDS and any(keyword in text_low for keyword in FILTER_KEYWORDS if keyword):
        return True
    
    return False

def extract_message_content(message):
    """Extrait le contenu textuel d'un message"""
    if message.text:
        return message.text
    elif message.caption:
        return message.caption
    elif message.document and message.document.file_name:
        return f"📄 {message.document.file_name}"
    else:
        return "[Contenu média sans texte]"

# ---------------- BOT ----------------
app = Client(
    name="forward_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    workers=100
)

# ---------------- HANDLER EN TEMPS RÉEL ----------------
@app.on_message(filters.chat(SOURCE_CHANNEL_ID if SOURCE_CHANNEL_ID else SOURCE_CHANNEL_USERNAME))
async def realtime_handler(client, message):
    """Gère les messages en temps réel (si le bot est dans le canal)"""
    msg_id = f"{message.chat.id}:{message.id}"
    
    if msg_id in posted:
        logger.debug(f"📭 Message {msg_id} déjà traité")
        return
    
    text = extract_message_content(message)
    logger.info(f"📩 Message reçu en temps réel: {message.id}")
    logger.debug(f"Contenu: {text[:100]}...")
    
    if should_filter_message(text):
        logger.info(f"⏭️ Message {message.id} filtré, ignoré")
        posted.add(msg_id)
        save_posted()
        return
    
    await forward_to_channels(client, message, text)
    
    posted.add(msg_id)
    save_posted()

# ---------------- FONCTION DE FORWARD ----------------
async def forward_to_channels(client, message, text):
    """Transfère le message vers tous les canaux de destination"""
    success_count = 0
    
    for idx, channel in enumerate(CHANNELS):
        try:
            # Différentes méthodes selon le type de message
            if message.photo:
                await client.send_photo(
                    chat_id=channel,
                    photo=message.photo.file_id,
                    caption=text[:1024] if text else None  # Limite de caption
                )
            elif message.video:
                await client.send_video(
                    chat_id=channel,
                    video=message.video.file_id,
                    caption=text[:1024] if text else None
                )
            elif message.document:
                await client.send_document(
                    chat_id=channel,
                    document=message.document.file_id,
                    caption=text[:1024] if text else None
                )
            elif message.animation:  # GIF
                await client.send_animation(
                    chat_id=channel,
                    animation=message.animation.file_id,
                    caption=text[:1024] if text else None
                )
            elif message.text:
                await client.send_message(
                    chat_id=channel,
                    text=text,
                    disable_web_page_preview=True
                )
            else:
                # Pour les autres types de média
                await message.copy(chat_id=channel)
            
            success_count += 1
            logger.info(f"✅ Envoyé vers {channel}")
            
            # Pause anti-flood entre chaque envoi
            if idx < len(CHANNELS) - 1:  # Pas de pause après le dernier
                await asyncio.sleep(1)  # Pause de 1 seconde
        
        except FloodWait as e:
            logger.warning(f"⏳ FloodWait {channel}, attente {e.value} secondes")
            await asyncio.sleep(e.value)
            # Réessayer après l'attente
            try:
                await message.copy(chat_id=channel)
                success_count += 1
                logger.info(f"✅ Envoyé vers {channel} après FloodWait")
            except Exception as retry_e:
                logger.error(f"❌ Erreur retry {channel}: {retry_e}")
        
        except Exception as e:
            logger.error(f"❌ Erreur {channel}: {e}")
    
    logger.info(f"📊 Résumé: {success_count}/{len(CHANNELS)} canaux atteints")

# ---------------- SCAN PERIODIQUE (BACKUP) ----------------
async def periodic_scanner():
    """Scanne périodiquement le canal source pour les messages manqués"""
    logger.info("🔄 Démarrage du scanner périodique")
    
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            
            logger.info("🔍 Scanner périodique en cours...")
            
            # Récupérer les derniers messages du canal
            try:
                if SOURCE_CHANNEL_ID:
                    messages = await app.get_chat_history(
                        chat_id=SOURCE_CHANNEL_ID,
                        limit=MAX_MESSAGES_PER_CHECK
                    )
                else:
                    messages = await app.get_chat_history(
                        chat_id=SOURCE_CHANNEL_USERNAME,
                        limit=MAX_MESSAGES_PER_CHECK
                    )
            except Exception as e:
                logger.error(f"❌ Impossible d'accéder au canal source: {e}")
                continue
            
            new_messages = 0
            
            # Traiter les messages du plus récent au plus ancien
            async for message in messages:
                msg_id = f"{message.chat.id}:{message.id}"
                
                if msg_id in posted:
                    continue  # Déjà traité
                
                text = extract_message_content(message)
                
                if should_filter_message(text):
                    posted.add(msg_id)
                    continue
                
                logger.info(f"📥 Message historique trouvé: {message.id}")
                await forward_to_channels(app, message, text)
                
                posted.add(msg_id)
                new_messages += 1
                
                # Petite pause pour éviter le flood
                await asyncio.sleep(0.5)
            
            if new_messages > 0:
                save_posted()
                logger.info(f"📈 {new_messages} nouveaux messages traités par scan")
            
        except Exception as e:
            logger.error(f"❌ Erreur scanner: {e}")
            await asyncio.sleep(30)  # Attendre en cas d'erreur

# ---------------- DÉMARRAGE AVEC SCANNER ----------------
@app.on_message(filters.command("start"))
async def start_command(client, message):
    """Commande /start pour vérifier l'état du bot"""
    status_msg = (
        f"🤖 Bot de republication actif\n\n"
        f"**Canal source:** `{SOURCE_CHANNEL}`\n"
        f"**Canaux destination:** `{len(CHANNELS)}`\n"
        f"**Messages traités:** `{len(posted)}`\n"
        f"**Intervalle de scan:** `{CHECK_INTERVAL}s`\n\n"
        f"Le bot surveille le canal et republie les messages "
        f"qui ne contiennent pas de liens HTTP ou de mots filtrés."
    )
    await message.reply(status_msg)

@app.on_message(filters.command("stats"))
async def stats_command(client, message):
    """Commande /stats pour afficher les statistiques"""
    stats_msg = (
        f"📊 **Statistiques du bot**\n\n"
        f"• Messages traités: `{len(posted)}`\n"
        f"• Canaux de destination: `{len(CHANNELS)}`\n"
        f"• Intervalle de scan: `{CHECK_INTERVAL}s`\n"
        f"• Dernière sauvegarde: `{time.ctime()}`"
    )
    await message.reply(stats_msg)

# ---------------- MAIN ----------------
async def main():
    """Fonction principale"""
    logger.info("=" * 50)
    logger.info("🤖 Bot de republication démarré")
    logger.info(f"📡 Canal source: {SOURCE_CHANNEL}")
    logger.info(f"🎯 Canaux destination: {len(CHANNELS)}")
    logger.info(f"⏱️ Intervalle de scan: {CHECK_INTERVAL}s")
    logger.info("=" * 50)
    
    # Démarrer le scanner périodique en tâche de fond
    scanner_task = asyncio.create_task(periodic_scanner())
    
    # Démarrer le client
    await app.start()
    
    # Afficher les infos du bot
    bot_info = await app.get_me()
    logger.info(f"Bot connecté: @{bot_info.username}")
    
    # Vérifier l'accès au canal source
    try:
        if SOURCE_CHANNEL_ID:
            chat = await app.get_chat(SOURCE_CHANNEL_ID)
        else:
            chat = await app.get_chat(SOURCE_CHANNEL_USERNAME)
        
        logger.info(f"✅ Accès au canal source: {chat.title}")
        
        # Vérifier si le bot peut voir les messages
        # (doit être admin ou membre pour les canaux privés)
        try:
            messages = await app.get_chat_history(chat.id, limit=1)
            async for _ in messages:
                pass
            logger.info("✅ Le bot peut lire les messages du canal")
        except Exception as e:
            logger.warning(f"⚠️ Le bot pourrait ne pas pouvoir lire les messages: {e}")
            logger.warning("Assurez-vous que le bot est admin du canal privé")
    
    except Exception as e:
        logger.error(f"❌ Impossible d'accéder au canal source: {e}")
    
    try:
        # Garder le bot en fonctionnement
        await asyncio.gather(
            scanner_task,
            app.run()
        )
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du bot...")
    finally:
        await app.stop()
        save_posted()
        logger.info("💾 Données sauvegardées")

if __name__ == "__main__":
    asyncio.run(main())