import os
import logging
from deep_translator import LibreTranslator, GoogleTranslator, PonsTranslator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Texte à traduire depuis variable d'environnement Railway
SOURCE_TEXT = os.getenv("SOURCE_TEXT", "Shameful and terrible look - the chaos that marred Senegal's Afcon triumph")

logger.info(f"Texte original : {SOURCE_TEXT}")

# Liste des traducteurs à tester
translators = {
    "LibreTranslator": lambda text: LibreTranslator(source='en', target='fr').translate(text),
    "GoogleTranslator": lambda text: GoogleTranslator(source='en', target='fr').translate(text),
    "PonsTranslator": lambda text: PonsTranslator(source='en', target='fr').translate(text),
    # DeepL gratuit peut échouer si pas de clé API, sinon utiliser DeepL(source='EN', target='FR', api_key=API_KEY)
    "DeepL": lambda text: DeepL(source='EN', target='FR').translate(text)
}

# Tester chaque traducteur
for name, func in translators.items():
    try:
        translated = func(SOURCE_TEXT)
        logger.info(f"✅ {name} : {translated}")
    except Exception as e:
        logger.error(f"❌ {name} erreur : {e}")
