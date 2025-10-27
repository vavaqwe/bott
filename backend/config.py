import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

class Config:
    # Admin
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    SESSION_SECRET = os.getenv('SESSION_SECRET', 'change_me_in_production')
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # XT Exchange - Account 2 (with balance)
    XT_API_KEY = os.getenv('XT_ACCOUNT_2_API_KEY') or os.getenv('XT_API_KEY')
    XT_API_SECRET = os.getenv('XT_ACCOUNT_2_API_SECRET') or os.getenv('XT_API_SECRET')
    XT_BASE_URL = 'https://sapi.xt.com'
    
    # Blockchain RPC
    ETH_RPC_URL = os.getenv('ETH_RPC_URL', 'https://eth.llamarpc.com')
    BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org')
    SOL_RPC_URL = os.getenv('SOL_RPC_URL', 'https://api.mainnet-beta.solana.com')
    
    # Trading settings
    ALLOW_LIVE_TRADING = os.getenv('ALLOW_LIVE_TRADING', 'False').lower() == 'true'
    MIN_SPREAD_PERCENT = float(os.getenv('MIN_SPREAD_PERCENT', '2.0'))
    MAX_SPREAD_PERCENT = float(os.getenv('MAX_SPREAD_PERCENT', '3.0'))
    MIN_LIQUIDITY_USD = float(os.getenv('MIN_LIQUIDITY_USD', '10000'))
    MIN_VOLUME_24H_USD = float(os.getenv('MIN_VOLUME_24H_USD', '50000'))
    
    # Bot settings
    PORT = int(os.getenv('PORT', '8000'))
    HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '30'))
    
    # DEX settings
    DEXSCREENER_BASE_URL = 'https://api.dexscreener.com/latest'
    
    # Database
    MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    DB_NAME = os.getenv('DB_NAME', 'test_database')

config = Config()