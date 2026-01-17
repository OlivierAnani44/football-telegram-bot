import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import PeerChannel

# Configuration
API_ID = 38191993  # Obtenez sur https://my.telegram.org
API_HASH = '1d26f45a4c703c9bbc96d3ede4737fad'
CHANNEL_USERNAME = 'Vinland_Saga_vf_fr'  # Sans @

async def monitor_channel_messages():
    """
    Surveiller les messages d'un canal avec Telethon
    (plus puissant pour la lecture seule)
    """
    client = TelegramClient('session_name', API_ID, API_HASH)
    
    await client.start()
    print("✅ Client connecté")
    
    try:
        # Rejoindre le canal
        channel = await client.get_entity(CHANNEL_USERNAME)
        print(f"📡 Canal : {channel.title}")
        
        # Pour les canaux publics, vous pouvez directement lire les messages
        # Pour les canaux privés, vous devez être membre
        
        # Récupérer les 20 derniers messages
        messages = await client.get_messages(channel, limit=20)
        
        print(f"\n📂 Derniers messages du canal :")
        for msg in reversed(messages):  # Du plus ancien au plus récent
            if msg.text:
                print(f"\n[{msg.date}]")
                print(f"{msg.text[:150]}...")
        
        print(f"\n👁️ Surveillance en temps réel...")
        
        # Surveiller les nouveaux messages
        @client.on(events.NewMessage(chats=channel))
        async def handler(event):
            print(f"\n📨 Nouveau message !")
            print(f"   Heure: {event.message.date}")
            print(f"   Message: {event.message.text[:200]}")
        
        # Lancer la surveillance
        await client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ Erreur : {e}")

# Lancer la surveillance
if __name__ == "__main__":
    asyncio.run(monitor_channel_messages())