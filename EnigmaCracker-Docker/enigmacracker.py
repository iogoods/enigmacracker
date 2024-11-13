import aiohttp
from aiogram import Bot
import asyncio
from datetime import datetime, timedelta
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
import logging
import time

# Logger configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Telegram credentials
TELEGRAM_TOKEN = "7706620947:AAGLGdTIKi4dB3irOtVmHD57f1Xxa8-ZIcs"
TELEGRAM_CHAT_ID = "1596333326"

# ElectrumX server URL
ELECTRUMX_SERVER_URL = "http://127.0.0.1:50002"

# Delay settings
DELAY_BETWEEN_REQUESTS = 0.1  # Delay between wallet checks

# Track the number of wallets scanned daily
wallets_scanned_today = 0

# Initialize the bot
bot = Bot(token=TELEGRAM_TOKEN)

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

async def check_btc_balance_async(address):
    """Check the BTC balance of an address asynchronously using ElectrumX server."""
    async with aiohttp.ClientSession() as session:
        url = f"{ELECTRUMX_SERVER_URL}/balance/{address}"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                balance = data.get("confirmed", 0) / 100000000  # Convert from Satoshi to BTC
                return balance
            return 0

async def notify_telegram_async(message):
    """Send a message to Telegram asynchronously."""
    await bot.send_message(TELEGRAM_CHAT_ID, message)

async def process_wallet_async(seed):
    """Process a single wallet asynchronously."""
    global wallets_scanned_today
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance_async(btc_address)
    wallets_scanned_today += 1  # Increment the wallet count
    
    # Notify if balance is found
    if btc_balance > 0:
        message = f"⚠️ Wallet with balance found!\n\nSeed: {seed}\nAddress: {btc_address}\nBalance: {btc_balance} BTC"
        await notify_telegram_async(message)

async def daily_summary():
    """Send a daily summary of the number of wallets scanned."""
    global wallets_scanned_today
    while True:
        # Calculate time until midnight to schedule the summary
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_run - now).total_seconds())
        
        # Send the daily summary
        summary_message = f"📊 Daily Wallet Scan Summary:\nTotal wallets scanned today: {wallets_scanned_today}"
        await notify_telegram_async(summary_message)
        
        # Reset the daily counter
        wallets_scanned_today = 0

async def main_async():
    """Main function to scan wallets and handle daily summary notifications."""
    # Generate a list of seeds to test
    seeds = [generate_bip39_seed() for _ in range(10)]
    
    # Schedule the daily summary coroutine to run in the background
    asyncio.create_task(daily_summary())
    
    # Scan wallets sequentially with delay
    for seed in seeds:
        await process_wallet_async(seed)
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

if __name__ == "__main__":
    # Run the main async loop
    asyncio.run(main_async())
