import sys
import os
import requests
import logging
import time
import asyncio
from dotenv import load_dotenv
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip44,
    Bip44Coins,
    Bip44Changes,
    Bip39WordsNum,
)
from aiohttp import ClientSession
from multiprocessing import Pool

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Konfiguration
LOG_FILE_NAME = "enigmacracker.log"
WALLETS_FILE_NAME = "wallets_with_balance.txt"
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILE_NAME)
WALLETS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), WALLETS_FILE_NAME)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ELECTRUMX_SERVER_URL = os.getenv("ELECTRUMX_SERVER_URL", "http://localhost:8000")

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),  # Log in eine Datei
        logging.StreamHandler(sys.stdout),  # Log in die Konsole
    ],
)

# Funktion, um die Telegram-Benachrichtigung zu senden
def send_telegram_notification(seed, BTC_address, BTC_balance):
    message = (
        f"(!) Wallet with balance found!\n\n"
        f"Seed: {seed}\n"
        f"BTC Address: {BTC_address}\n"
        f"Balance: {BTC_balance} BTC"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            logging.info("Telegram notification sent successfully.")
        else:
            logging.error(f"Failed to send Telegram notification. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error sending Telegram notification: {str(e)}")

# BIP39 Mnemonic Generator (12-Wort-Mnemonic)
def bip():
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

# BIP44 Bitcoin-Adresse aus dem Seed generieren
def bip44_BTC_seed_to_address(seed):
    seed_bytes = Bip39SeedGenerator(seed).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)
    return bip44_addr_ctx.PublicKey().ToAddress()

# BTC-Balance mithilfe der ElectrumX-Node abfragen (asynchron)
async def check_balance_async(address: str, session: ClientSession) -> float:
    try:
        async with session.post(ELECTRUMX_SERVER_URL, json={
            "method": "blockchain.address.get_balance",
            "params": [address]
        }) as response:
            data = await response.json()
            balance = data['result']['confirmed'] / 100000000  # Umwandlung von Satoshi in Bitcoin
            return balance
    except Exception as e:
        logging.error(f"Error checking BTC balance for address {address}: {str(e)}")
        return 0

# Verarbeitung eines einzelnen Seeds
async def process_wallet_async(seed: str, session: ClientSession):
    BTC_address = bip44_BTC_seed_to_address(seed)
    BTC_balance = await check_balance_async(BTC_address, session)

    logging.info(f"Seed: {seed}")
    logging.info(f"BTC Address: {BTC_address}")
    logging.info(f"BTC Balance: {BTC_balance} BTC")

    if BTC_balance > 0:
        logging.info("(!) Wallet with BTC balance found!")
        write_to_file(seed, BTC_address, BTC_balance)

# Schreibe Informationen in eine Datei und sende Telegram-Nachricht
def write_to_file(seed: str, BTC_address: str, BTC_balance: float):
    with open(WALLETS_FILE_PATH, "a") as f:
        log_message = (
            f"Seed: {seed}\n"
            f"BTC Address: {BTC_address}\nBalance: {BTC_balance} BTC\n\n"
        )
        f.write(log_message)
        logging.info(f"Written to file: {log_message}")
    
    send_telegram_notification(seed, BTC_address, BTC_balance)

# Funktion für Multiprocessing (verwende mehrere Kerne)
def process_wallet_multiprocessing(seed: str):
    asyncio.run(process_wallet_async(seed, session))

# Hauptprogramm mit Multiprocessing und AsyncIO
async def main():
    # Erstelle eine asynchrone Client-Session für parallele HTTP-Anfragen
    async with ClientSession() as session:
        # Initialisiere den Multiprocessing-Pool
        with Pool(processes=16) as pool:  # 16 Prozesse, um die 16 Kerne des Servers zu nutzen
            while True:
                seeds = [bip() for _ in range(16)]  # Erzeuge 16 Wallets gleichzeitig
                pool.map(process_wallet_multiprocessing, seeds)  # Verarbeite die Wallets parallel

if __name__ == "__main__":
    asyncio.run(main())
