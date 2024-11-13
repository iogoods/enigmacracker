import os
import asyncio
import aiohttp
import logging
import multiprocessing
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
from aiogram import Bot
import time

# Logger-Konfiguration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Telegram-Token und Chat-ID direkt im Code definieren
TELEGRAM_TOKEN = "your_telegram_token"
CHAT_ID = "your_chat_id"
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

async def check_btc_balance(address):
    retry_attempts = 3
    for attempt in range(retry_attempts):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ELECTRUMX_SERVER_URL}/address/{address}") as response:
                    data = await response.json()
                    balance = data.get("confirmed", 0) / 100000000  # Satoshi zu BTC
                    return balance
        except asyncio.TimeoutError:
            logging.warning(f"Timeout bei Versuch {attempt + 1} für Adresse {address}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(1)  # Kurze Verzögerung und erneuter Versuch
            else:
                logging.error(f"Timeout erreicht für Adresse {address}")
        except Exception as e:
            logging.error(f"Fehler bei der Abfrage für Adresse {address}: {e}")
            break
    return 0

async def process_wallet_async(seed):
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance(btc_address)
    if btc_balance > 0:
        logging.info(f"Wallet mit Balance gefunden: {btc_address} - Balance: {btc_balance} BTC")
        await notify_telegram(seed, btc_address, btc_balance)

async def process_wallets_batch(seeds):
    tasks = [asyncio.create_task(process_wallet_async(seed)) for seed in seeds]
    await asyncio.gather(*tasks)

def process_wallets_multiprocessing(seeds):
    asyncio.run(process_wallets_batch(seeds))

async def main():
    while True:  # Endlosschleife
        seeds = [generate_bip39_seed() for _ in range(1000)]  # 1000 Seeds pro Zyklus
        with multiprocessing.Pool() as pool:
            pool.map(process_wallets_multiprocessing, [seeds[i:i + 100] for i in range(0, len(seeds), 100)])

if __name__ == "__main__":
    asyncio.run(main())
