import requests
import time
import hmac
import hashlib
from typing import Optional, Dict, List
from utils import setup_logging, retry_on_failure, measure_latency
from config import config

logger = setup_logging(__name__)

class XTClient:
    """Client for XT.com exchange API"""
    
    def __init__(self):
        self.api_key = config.XT_API_KEY
        self.api_secret = config.XT_API_SECRET
        self.base_url = config.XT_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-MBX-APIKEY': self.api_key
        })
        logger.info("XT Client initialized")
    
    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    @retry_on_failure(max_retries=3, delay=1.0)
    @measure_latency
    def get_symbols(self) -> List[Dict]:
        """Get all trading symbols"""
        try:
            url = f"{self.base_url}/v4/public/symbol"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('rc') == 0:
                symbols = data.get('result', [])
                logger.info(f"Fetched {len(symbols)} symbols from XT")
                return symbols
            else:
                logger.error(f"XT API error: {data}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch symbols: {e}")
            return []
    
    @retry_on_failure(max_retries=3, delay=1.0)
    @measure_latency
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker price for a symbol"""
        try:
            url = f"{self.base_url}/v4/public/ticker/price"
            params = {'symbol': symbol}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('rc') == 0:
                result = data.get('result', {})
                # Handle if result is a list, take first element
                if isinstance(result, list):
                    if len(result) > 0:
                        logger.debug(f"Ticker for {symbol}: {result[0]}")
                        return result[0]
                    else:
                        logger.warning(f"Empty result list for {symbol}")
                        return None
                elif isinstance(result, dict):
                    logger.debug(f"Ticker for {symbol}: {result}")
                    return result
                else:
                    logger.warning(f"Unexpected result type for {symbol}: {type(result)}")
                    return None
            else:
                logger.warning(f"Failed to get ticker for {symbol}: {data}")
                return None
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=1.0)
    @measure_latency
    def get_orderbook(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Get orderbook depth"""
        try:
            url = f"{self.base_url}/v4/public/depth"
            params = {'symbol': symbol, 'limit': limit}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('rc') == 0:
                result = data.get('result', {})
                logger.debug(f"Orderbook for {symbol}: {len(result.get('bids', []))} bids, {len(result.get('asks', []))} asks")
                return result
            else:
                logger.warning(f"Failed to get orderbook for {symbol}: {data}")
                return None
        except Exception as e:
            logger.error(f"Failed to get orderbook for {symbol}: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=1.0)
    @measure_latency
    def get_balance(self) -> Optional[Dict]:
        """Get account balance"""
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp}
            params['signature'] = self._generate_signature(params)
            
            url = f"{self.base_url}/v4/balances"
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('rc') == 0:
                logger.info("Balance fetched successfully")
                return data.get('result', {})
            else:
                logger.error(f"Failed to get balance: {data}")
                return None
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: float, price: Optional[float] = None) -> Optional[Dict]:
        """Place an order"""
        if not config.ALLOW_LIVE_TRADING:
            logger.warning("Live trading is disabled. Order not placed.")
            return None
        
        try:
            timestamp = int(time.time() * 1000)
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': quantity,
                'timestamp': timestamp
            }
            
            if price and order_type.upper() == 'LIMIT':
                params['price'] = price
                params['timeInForce'] = 'GTC'
            
            params['signature'] = self._generate_signature(params)
            
            url = f"{self.base_url}/v4/order"
            response = self.session.post(url, json=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('rc') == 0:
                logger.info(f"Order placed: {symbol} {side} {quantity}")
                return data.get('result', {})
            else:
                logger.error(f"Failed to place order: {data}")
                return None
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None
    
    def find_symbol_by_address(self, address: str) -> Optional[str]:
        """Find XT symbol by token contract address"""
        # This is a simplified lookup - in production, you'd maintain a mapping
        symbols = self.get_symbols()
        address_lower = address.lower()
        
        for symbol_data in symbols:
            # Check if symbol data contains address info
            if 'baseAsset' in symbol_data:
                base_asset = symbol_data['baseAsset'].upper()
                symbol = symbol_data.get('symbol', '')
                # Try matching common patterns
                if address_lower in symbol.lower():
                    return symbol
        
        logger.warning(f"No symbol found for address {address}")
        return None