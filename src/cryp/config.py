# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

    # Encryption
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    
    # MongoDB
    MONGODB_URI = os.getenv('MONGODB_URI')
    MONGODB_DB = os.getenv('MONGODB_DB', 'crypto_payments')
    
    # Blockchain
    BSC_RPC_URL = os.getenv('BSC_RPC_URL')
    BSC_TESTNET_RPC_URL = os.getenv('BSC_TESTNET_RPC_URL')
    PAYMENT_PRIVATE_KEY = os.getenv('PAYMENT_PRIVATE_KEY')
    
    # Alchemy
    ALCHEMY_WEBHOOK_SIGNING_KEY = os.getenv('ALCHEMY_WEBHOOK_SIGNING_KEY')
    ALCHEMY_AUTH_TOKEN = os.getenv('Alchemy_Auth_Token')
    ALCHEMY_WEBHOOK_ID = os.getenv('ALCHEMY_WEBHOOK_ID')
    
    # Payment settings
    PAYMENT_TIMEOUT_MINUTES = 30
    CONFIRMATIONS_REQUIRED = 12  # BSC confirmations
    
    # # Token addresses (BSC Mainnet)
    # USDT_CONTRACT = '0x55d398326f99059fF775485246999027B3197955'
    # USDC_CONTRACT = '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d'
    # BUSD_CONTRACT = '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56'

    # BSC Testnet Token/Contract Addresses (Chain ID: 97)
    BSC_TESTNET_TOKENS = {
        'USDT': '0x337610d27c682E347C9cD60BD4b3b107C9d34dDd',
        'BUSD': '0xeD24FC36d5Ee211Ea25A80239Fb8C4Cfd80f12Ee',
        'USDC': '0x64544969ed7EBf5f083679233325356EbE738930',
    }
    
    # BSC Mainnet Token Addresses (Chain ID: 56)
    BSC_MAINNET_TOKENS = {
        'USDT': '0x55d398326f99059fF775485246999027B3197955',
        'BUSD': '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56',
        'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',
    }
    