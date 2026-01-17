# POSTED_FILE = "posted.json"
# print("POSTED_FILE =", POSTED_FILE)
import os
import json
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest

# ---------------- CONFIG ----------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")
CHANNELS_RAW = os.getenv("CHANNELS")

POSTED_FILE = "posted.json"   # ✅ DOIT ÊTRE AVANT load_posted()

if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, CHANNELS_RAW]):
    raise RuntimeError("❌ Variables d'environnement manquantes")

API_ID = int(API_ID)

# SOURCE CHANNEL
if SOURCE_CHANNEL.startswith("@"):
    SOURCE_CHANNEL = SOURCE_CHANNEL
else:
    SOURCE_CHANNEL = int(SOURCE_CHANNEL)

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
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f)

posted = load_posted()

# ---------------- TELETHON CLIENT ----------------
# Pour Telethon, on utilise l'API utilisateur pour lire les messages
# mais on peut aussi utiliser le bot pour envoyer
client = TelegramClient(
    'footforward_bot_session', 
    api_id=API_ID, 
    api_hash=API_HASH
).start(bot_token=BOT_TOKEN)

# ---------------- JOIN CHANNELS ----------------
async def join_channels():
    """Rejoindre tous les canaux nécessaires"""
    logger.info("🔗 Connexion aux canaux...")
    
    try:
        # Rejoindre le canal source (pour pouvoir le lire)
        if isinstance(SOURCE_CHANNEL, str) and SOURCE_CHANNEL.startswith("@"):
            await client(JoinChannelRequest(channel=SOURCE_CHANNEL))
            logger.info(f"✅ Rejoint le canal source: {SOURCE_CHANNEL}")
        else:
            # Pour les IDs numériques, on essaie de se connecter
            entity = await client.get_entity(SOURCE_CHANNEL)
            logger.info(f"✅ Connecté au canal source: {entity.title}")
    except Exception as e:
        logger.warning(f"⚠️ Canal source: {e}")
    
    # Rejoindre les canaux de destination (pour pouvoir y poster)
    for channel in CHANNELS:
        try:
            if isinstance(channel, str) and channel.startswith("@"):
                await client(JoinChannelRequest(channel=channel))
                logger.info(f"✅ Rejoint: {channel}")
            else:
                entity = await client.get_entity(channel)
                logger.info(f"✅ Connecté à: {entity.title}")
        except Exception as e:
            logger.warning(f"⚠️ Erreur avec {channel}: {e}")
    
    logger.info("✅ Tous les canaux connectés")

# ---------------- HANDLER ----------------
@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    """Gérer les nouveaux messages du canal source"""
    message = event.message
    logger.info(f"📩 Message reçu: {message.id}")
    
    msg_id = str(message.id)
    if msg_id in posted:
        logger.info(f"⏭️ Message déjà posté: {message.id}")
        return
    
    # Récupérer le texte
    text = message.text or message.caption
    if not text:
        logger.info(f"📷 Message média sans texte: {message.id}")
        return
    
    # Filtrer les messages avec liens ou mots-clés
    text_low = text.lower()
    if "http" in text_low or "aten10" in text_low:
        logger.info(f"🚫 Message filtré: {message.id}")
        return
    
    # Poster dans tous les canaux de destination
    for channel in CHANNELS:
        try:
            if message.photo:
                # Pour les photos avec légende
                if message.caption:
                    await client.send_file(
                        channel,
                        message.photo,
                        caption=message.caption
                    )
                else:
                    await client.send_file(channel, message.photo)
            elif message.video:
                # Pour les vidéos
                await client.send_file(
                    channel,
                    message.video,
                    caption=message.caption
                )
            elif message.document:
                # Pour les documents
                await client.send_file(
                    channel,
                    message.document,
                    caption=message.caption
                )
            else:
                # Pour les messages texte uniquement
                await client.send_message(channel, text)
            
            logger.info(f"✅ Envoyé vers {channel}")
            
        except Exception as e:
            logger.error(f"❌ Erreur avec {channel}: {e}")
            # Essayer avec une autre méthode si la première échoue
            try:
                await client.send_message(channel, f"📨 Message du canal source:\n\n{text}")
                logger.info(f"✅ Message texte envoyé vers {channel}")
            except Exception as e2:
                logger.error(f"❌ Échec total avec {channel}: {e2}")
        
        # Pause pour éviter de spammer l'API
        await asyncio.sleep(1)
    
    # Marquer comme posté et sauvegarder
    posted.add(msg_id)
    save_posted()
    logger.info(f"✅ Message {message.id} traité et sauvegardé")

# ---------------- STARTUP ----------------
async def main():
    """Fonction principale"""
    logger.info("🤖 Démarrage du bot Telethon...")
    
    # Se connecter aux canaux
    await join_channels()
    
    # Obtenir les infos du canal source
    try:
        entity = await client.get_entity(SOURCE_CHANNEL)
        logger.info(f"🎯 Surveillance du canal: {entity.title} (ID: {entity.id})")
    except Exception as e:
        logger.error(f"❌ Impossible d'accéder au canal source: {e}")
        return
    
    # Afficher les canaux de destination
    logger.info(f"📤 Canaux de destination: {len(CHANNELS)}")
    for i, channel in enumerate(CHANNELS, 1):
        try:
            entity = await client.get_entity(channel)
            logger.info(f"  {i}. {entity.title}")
        except:
            logger.info(f"  {i}. {channel}")
    
    logger.info("👂 En écoute des nouveaux messages...")
    logger.info("Appuyez sur Ctrl+C pour arrêter")
    
    # Garder le bot actif
    await client.run_until_disconnected()

# ---------------- RAILWAY CONFIG ----------------
if __name__ == "__main__":
    # Configuration pour Railway
    logger.info("🚂 Démarrage sur Railway...")
    logger.info(f"POSTED_FILE = {POSTED_FILE}")
    logger.info(f"API_ID = {API_ID}")
    logger.info(f"SOURCE_CHANNEL = {SOURCE_CHANNEL}")
    logger.info(f"NOMBRE DE CANAUX = {len(CHANNELS)}")
    
    # Créer le fichier posted.json s'il n'existe pas
    if not os.path.exists(POSTED_FILE):
        save_posted()
        logger.info(f"✅ Fichier {POSTED_FILE} créé")
    
    # Lancer le bot
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Bot arrêté par l'utilisateur")
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")
    finally:
        logger.info("👋 Bot terminé")

'''
POSTED_FILE = "posted.json"
print("POSTED_FILE =", POSTED_FILE)
import os
import json
import logging
import asyncio
from pyrogram import Client, filters

# ---------------- CONFIG ----------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")
CHANNELS_RAW = os.getenv("CHANNELS")

POSTED_FILE = "posted.json"   # ✅ DOIT ÊTRE AVANT load_posted()

if not all([API_ID, API_HASH, BOT_TOKEN, SOURCE_CHANNEL, CHANNELS_RAW]):
    raise RuntimeError("❌ Variables d'environnement manquantes")

API_ID = int(API_ID)

# SOURCE CHANNEL
if SOURCE_CHANNEL.startswith("@"):
    SOURCE_CHANNEL = SOURCE_CHANNEL
else:
    SOURCE_CHANNEL = int(SOURCE_CHANNEL)

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
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted():
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f)

posted = load_posted()

# ---------------- BOT ----------------
app = Client(
    name="football_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ---------------- HANDLER ----------------
@app.on_message(filters.chat(SOURCE_CHANNEL))
async def handler(client, message):
    logger.info(f"📩 Message reçu: {message.id}")

    msg_id = str(message.id)
    if msg_id in posted:
        return

    text = message.text or message.caption
    if not text:
        return

    text_low = text.lower()
    if "http" in text_low or "aten10" in text_low:
        return

    for ch in CHANNELS:
        try:
            if message.photo:
                await client.send_photo(
                    chat_id=ch,
                    photo=message.photo.file_id,
                    caption=text
                )
            else:
                await client.send_message(ch, text)

            logger.info(f"✅ Envoyé vers {ch}")
        except Exception as e:
            logger.error(f"❌ Erreur {ch}: {e}")

        await asyncio.sleep(0.6)

    posted.add(msg_id)
    save_posted()

# ---------------- START ----------------
if __name__ == "__main__":
    logger.info("🤖 Bot démarré et en écoute...")
    app.run()
'''