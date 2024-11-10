import sys
import os
import logging
import time
import json
from dotenv import load_dotenv
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip44,
    Bip44Coins,
    Bip44Changes,
    Bip39WordsNum,
)
from jsonrpcclient import request as rpc_request
import requests

# Constants
LOG_FILE_NAME = "enigmacracker.log"
ENV_FILE_NAME = "EnigmaCracker.env"
WALLETS_FILE_NAME = "wallets_with_balance.txt"

# Get the absolute path of the directory where the script is located
directory = os.path.dirname(os.path.abspath(__file__))
# Initialize directory paths
log_file_path = os.path.join(directory, LOG_FILE_NAME)
env_file_path = os.path.join(directory, ENV_FILE_NAME)
wallets_file_path = os.path.join(directory, WALLETS_FILE_NAME)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),  # Log to a file
        logging.StreamHandler(sys.stdout),   # Log to standard output
    ],
)

# Load environment variables from .env file
load_dotenv(env_file_path)

# ElectrumX server URL
ELECTRUMX_SERVER_URL = os.getenv("ELECTRUMX_SERVER_URL", "http://localhost:50001")

def bip():
    # Generate a 12-word BIP39 mnemonic
    return Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12)

def bip44_BTC_seed_to_address(seed):
    # Generate the seed from the mnemonic
    seed_bytes = Bip39SeedGenerator(seed).Generate()

    # Generate the Bip44 object
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)

    # Generate the Bip44 address (account 0, change 0, address 0)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_chg_ctx.AddressIndex(0)

    # Return the BTC address
    return bip44_addr_ctx.PublicKey().ToAddress()

def check_BTC_balance(address):
    # Use ElectrumX server to get the balance of the BTC address
    try:
        response = rpc_request(ELECTRUMX_SERVER_URL, "blockchain.address.get_balance", address)
        balance_info = response.json().get("result", {})
        confirmed_balance = balance_info.get("confirmed", 0)
        
        # Convert satoshi to bitcoin
        return confirmed_balance / 100000000  
    except Exception as e:
        logging.error(f"Error checking BTC balance via ElectrumX: {str(e)}")
        return 0

def write_to_file(seed, BTC_address, BTC_balance):
    # Write the seed, address, and BTC balance to a file in the script's directory
    with open(wallets_file_path, "a") as f:
        log_message = (
            f"Seed: {seed}\n\n"                 # Seed in a new line
            f"BTC Address: {BTC_address}\nBalance: {BTC_balance} BTC\n\n"  # BTC address and balance
        )
        f.write(log_message)
        logging.info(f"Written to file: {log_message}")

def main():
    try:
        while True:
            seed = bip()
            # BTC
            BTC_address = bip44_BTC_seed_to_address(seed)
            BTC_balance = check_BTC_balance(BTC_address)

            logging.info(f"Seed: {seed}")
            logging.info(f"BTC address: {BTC_address}")
            logging.info(f"BTC balance: {BTC_balance} BTC")

            # Check if the BTC address has a balance
            if BTC_balance > 0:
                logging.info("(!) Wallet with BTC balance found!")
                write_to_file(seed, BTC_address, BTC_balance)

    except KeyboardInterrupt:
        logging.info("Program interrupted by user. Exiting...")

if __name__ == "__main__":
    main()
