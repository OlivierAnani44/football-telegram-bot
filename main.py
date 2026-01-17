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
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutes par défaut
MAX_MESSAGES_PER_CHECK = int(os.getenv("MAX_MESSAGES_PER_CHECK", "20"))
FILTER_KEYWORDS = os.getenv("FILTER_KEYWORDS", "").lower().split(",")

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
                return set(data.get("posted_ids", []))
        except Exception as e:
            logger.error(f"❌ Erreur lecture {POSTED_FILE}: {e}")
            return set()
    return set()

def save_posted():
    try:
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
    
    if "http" in text_low or "aten10" in text_low:
        return True
    
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

# ---------------- GESTION FLOOD WAIT ----------------
async def safe_start_client():
    """Démarre le client avec gestion FloodWait"""
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            app = Client(
                name="forward_bot_session",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True,
                workers=50
            )
            
            await app.start()
            logger.info("✅ Client démarré avec succès")
            return app
            
        except FloodWait as e:
            wait_time = e.value
            logger.warning(f"⏳ FloodWait détecté: {wait_time} secondes")
            
            if attempt < max_retries - 1:
                logger.info(f"🔄 Nouvelle tentative dans {wait_time} secondes...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Trop de tentatives, attente de {wait_time} secondes")
                await asyncio.sleep(wait_time)
                # Dernière tentative
                app = Client(
                    name="forward_bot_session_final",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    bot_token=BOT_TOKEN,
                    in_memory=True
                )
                await app.start()
                return app
                
        except Exception as e:
            logger.error(f"❌ Erreur démarrage client (tentative {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                raise e
    
    raise Exception("Échec démarrage client après plusieurs tentatives")

# ---------------- FONCTION DE FORWARD ----------------
async def forward_to_channels(client, message, text):
    """Transfère le message vers tous les canaux de destination"""
    success_count = 0
    
    for idx, channel in enumerate(CHANNELS):
        try:
            if message.photo:
                await client.send_photo(
                    chat_id=channel,
                    photo=message.photo.file_id,
                    caption=text[:1024] if text else None
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
            elif message.text:
                await client.send_message(
                    chat_id=channel,
                    text=text,
                    disable_web_page_preview=True
                )
            else:
                await message.copy(chat_id=channel)
            
            success_count += 1
            logger.info(f"✅ Envoyé vers {channel}")
            
            if idx < len(CHANNELS) - 1:
                await asyncio.sleep(1)
        
        except FloodWait as e:
            logger.warning(f"⏳ FloodWait {channel}, attente {e.value} secondes")
            await asyncio.sleep(e.value)
            continue
            
        except Exception as e:
            logger.error(f"❌ Erreur {channel}: {e}")
    
    logger.info(f"📊 {success_count}/{len(CHANNELS)} canaux atteints")

# ---------------- SCAN PERIODIQUE ----------------
async def periodic_scanner(app):
    """Scanne périodiquement le canal source"""
    logger.info("🔄 Scanner périodique démarré")
    
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            
            logger.info("🔍 Scanner périodique en cours...")
            
            # Vérifier si le client est connecté
            if not app.is_connected:
                logger.warning("⚠️ Client déconnecté, tentative reconnexion...")
                await app.stop()
                await asyncio.sleep(5)
                app = await safe_start_client()
            
            # Récupérer les messages
            try:
                if SOURCE_CHANNEL_ID:
                    messages = app.get_chat_history(
                        SOURCE_CHANNEL_ID,
                        limit=MAX_MESSAGES_PER_CHECK
                    )
                else:
                    messages = app.get_chat_history(
                        SOURCE_CHANNEL_USERNAME,
                        limit=MAX_MESSAGES_PER_CHECK
                    )
            except Exception as e:
                logger.error(f"❌ Erreur récupération messages: {e}")
                continue
            
            new_messages = 0
            async for message in messages:
                msg_id = f"{message.chat.id}:{message.id}"
                
                if msg_id in posted:
                    continue
                
                text = extract_message_content(message)
                
                if should_filter_message(text):
                    posted.add(msg_id)
                    continue
                
                logger.info(f"📥 Message historique: {message.id}")
                await forward_to_channels(app, message, text)
                
                posted.add(msg_id)
                new_messages += 1
                await asyncio.sleep(0.5)
            
            if new_messages > 0:
                save_posted()
                logger.info(f"📈 {new_messages} nouveaux messages traités")
            
        except FloodWait as e:
            logger.warning(f"⏳ FloodWait scanner: {e.value} secondes")
            await asyncio.sleep(e.value)
            
        except Exception as e:
            logger.error(f"❌ Erreur scanner: {e}")
            await asyncio.sleep(30)

# ---------------- HANDLER TEMPS RÉEL ----------------
@app.on_message(filters.chat(SOURCE_CHANNEL_ID if SOURCE_CHANNEL_ID else SOURCE_CHANNEL_USERNAME))
async def realtime_handler(client, message):
    """Gère les messages en temps réel"""
    msg_id = f"{message.chat.id}:{message.id}"
    
    if msg_id in posted:
        return
    
    text = extract_message_content(message)
    logger.info(f"📩 Message temps réel: {message.id}")
    
    if should_filter_message(text):
        posted.add(msg_id)
        save_posted()
        return
    
    await forward_to_channels(client, message, text)
    
    posted.add(msg_id)
    save_posted()

# ---------------- COMMANDES ----------------
@app.on_message(filters.command("start"))
async def start_command(client, message):
    status_msg = (
        f"🤖 Bot de republication actif\n\n"
        f"**Canal source:** `{SOURCE_CHANNEL}`\n"
        f"**Canaux destination:** `{len(CHANNELS)}`\n"
        f"**Messages traités:** `{len(posted)}`\n"
        f"**Intervalle scan:** `{CHECK_INTERVAL}s`"
    )
    await message.reply(status_msg)

@app.on_message(filters.command("stats"))
async def stats_command(client, message):
    stats_msg = (
        f"📊 **Statistiques**\n\n"
        f"• Messages traités: `{len(posted)}`\n"
        f"• Canaux destination: `{len(CHANNELS)}`\n"
        f"• Dernière sauvegarde: `{time.ctime()}`"
    )
    await message.reply(stats_msg)

# ---------------- MAIN ----------------
async def main():
    """Fonction principale avec gestion robuste"""
    logger.info("=" * 50)
    logger.info("🤖 Bot de republication démarré")
    logger.info(f"📡 Canal source: {SOURCE_CHANNEL}")
    logger.info(f"🎯 Canaux destination: {len(CHANNELS)}")
    logger.info(f"⏱️ Intervalle scan: {CHECK_INTERVAL}s")
    logger.info("=" * 50)
    
    # Attendre un peu avant de démarrer (pour éviter FloodWait immédiat)
    initial_wait = int(os.getenv("INITIAL_WAIT", "10"))
    logger.info(f"⏳ Attente initiale de {initial_wait} secondes...")
    await asyncio.sleep(initial_wait)
    
    # Démarrer le client avec gestion FloodWait
    app = await safe_start_client()
    
    # Vérifier l'accès au canal
    try:
        if SOURCE_CHANNEL_ID:
            chat = await app.get_chat(SOURCE_CHANNEL_ID)
        else:
            chat = await app.get_chat(SOURCE_CHANNEL_USERNAME)
        
        logger.info(f"✅ Accès canal source: {chat.title}")
        
        # Vérifier si le bot est dans le canal
        try:
            member = await app.get_chat_member(chat.id, "me")
            logger.info(f"👤 Statut bot dans canal: {member.status}")
            
            if member.status not in ["administrator", "member", "creator"]:
                logger.warning("⚠️ Bot n'est pas membre/admin du canal")
                logger.warning("Il ne pourra pas voir les messages en temps réel")
                logger.warning("Le scanner périodique tentera d'accéder aux messages")
        except Exception as e:
            logger.warning(f"⚠️ Bot pas dans le canal: {e}")
            
    except Exception as e:
        logger.error(f"❌ Erreur accès canal: {e}")
        logger.warning("⚠️ Le scanner pourra échouer")
    
    # Démarrer le scanner en tâche de fond
    scanner_task = asyncio.create_task(periodic_scanner(app))
    
    # Maintenir le bot actif
    try:
        # Afficher un message de démarrage
        bot_info = await app.get_me()
        logger.info(f"✅ Bot @{bot_info.username} prêt")
        
        # Boucle principale
        while True:
            try:
                # Vérifier la connexion périodiquement
                if not app.is_connected:
                    logger.warning("⚠️ Déconnexion détectée, reconnexion...")
                    await app.stop()
                    await asyncio.sleep(10)
                    app = await safe_start_client()
                
                await asyncio.sleep(60)  # Vérifier toutes les minutes
                
            except KeyboardInterrupt:
                logger.info("🛑 Arrêt demandé...")
                break
            except Exception as e:
                logger.error(f"❌ Erreur boucle principale: {e}")
                await asyncio.sleep(30)
                
    finally:
        # Nettoyage
        logger.info("🧹 Nettoyage en cours...")
        scanner_task.cancel()
        try:
            await scanner_task
        except asyncio.CancelledError:
            pass
            
        if app.is_connected:
            await app.stop()
            
        save_posted()
        logger.info("💾 Données sauvegardées")
        logger.info("👋 Bot arrêté")

if __name__ == "__main__":
    # Créer l'application Pyrogram
    app = Client(
        name="forward_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
        workers=50
    )
    
    # Exécuter le bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt par utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")