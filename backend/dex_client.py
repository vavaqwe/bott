import requests
from typing import Optional, Dict, List
from utils import setup_logging, retry_on_failure, measure_latency
from config import config
import time

logger = setup_logging(__name__)

class DexClient:
    """Client for DEXScreener API"""
    
    def __init__(self):
        self.base_url = config.DEXSCREENER_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # 1 second between requests
        logger.info("DEX Client initialized")
    
    def _rate_limit(self):
        """Simple rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @measure_latency
    def get_token_info(self, chain: str, address: str) -> Optional[Dict]:
        """Get token info from DEXScreener"""
        try:
            self._rate_limit()
            url = f"{self.base_url}/dex/tokens/{address}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if 'pairs' in data and len(data['pairs']) > 0:
                # Return the first pair with best liquidity
                pairs = sorted(data['pairs'], key=lambda x: float(x.get('liquidity', {}).get('usd', 0)), reverse=True)
                logger.info(f"Found {len(pairs)} pairs for {address[:8]}... on {chain}")
                # Return just the first/best pair as a dict, not list
                return pairs[0] if pairs else None
            else:
                logger.warning(f"No pairs found for {address}")
                return None
        except Exception as e:
            logger.error(f"Failed to get token info for {address}: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @measure_latency
    def search_pairs(self, query: str) -> List[Dict]:
        """Search for pairs by query"""
        try:
            self._rate_limit()
            url = f"{self.base_url}/dex/search"
            params = {'q': query}
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            pairs = data.get('pairs', [])
            logger.info(f"Found {len(pairs)} pairs for query '{query}'")
            return pairs
        except Exception as e:
            logger.error(f"Failed to search pairs for {query}: {e}")
            return []
    
    @retry_on_failure(max_retries=3, delay=2.0)
    @measure_latency
    def get_latest_pairs(self) -> List[Dict]:
        """Get latest token pairs across all chains"""
        try:
            self._rate_limit()
            # Use correct endpoint for latest boosted tokens
            url = f"https://api.dexscreener.com/token-boosts/latest/v1"
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 404:
                # Fallback to search for popular tokens
                logger.warning("Latest pairs endpoint not available, using search fallback")
                return self._get_trending_pairs()
            
            response.raise_for_status()
            data = response.json()
            
            # Extract pairs from boosted tokens
            pairs = []
            if isinstance(data, list):
                for item in data:
                    if 'tokenAddress' in item:
                        # Get token info for each boosted token
                        token_pairs = self.get_token_info('ethereum', item['tokenAddress'])
                        if token_pairs:
                            pairs.append(token_pairs)
            
            logger.info(f"Fetched {len(pairs)} latest pairs")
            return pairs[:50]  # Limit to 50
        except Exception as e:
            logger.error(f"Failed to get latest pairs: {e}")
            return self._get_trending_pairs()
    
    def _get_trending_pairs(self) -> List[Dict]:
        """Fallback method to get trending pairs"""
        try:
            # Search for popular tokens as fallback
            popular_tokens = ['PEPE', 'SHIB', 'DOGE', 'FLOKI', 'WOJAK']
            pairs = []
            for token in popular_tokens:
                search_results = self.search_pairs(token)
                if search_results:
                    pairs.extend(search_results[:5])
            return pairs[:30]
        except Exception as e:
            logger.error(f"Failed to get trending pairs: {e}")
            return []
    
    def extract_pair_data(self, pair: Dict) -> Dict:
        """Extract relevant data from pair object"""
        try:
            return {
                'chain': pair.get('chainId', ''),
                'dex': pair.get('dexId', ''),
                'pair_address': pair.get('pairAddress', ''),
                'base_token': {
                    'address': pair.get('baseToken', {}).get('address', ''),
                    'name': pair.get('baseToken', {}).get('name', ''),
                    'symbol': pair.get('baseToken', {}).get('symbol', ''),
                },
                'quote_token': {
                    'address': pair.get('quoteToken', {}).get('address', ''),
                    'symbol': pair.get('quoteToken', {}).get('symbol', ''),
                },
                'price_usd': float(pair.get('priceUsd', 0)),
                'price_native': float(pair.get('priceNative', 0)),
                'liquidity': {
                    'usd': float(pair.get('liquidity', {}).get('usd', 0)),
                    'base': float(pair.get('liquidity', {}).get('base', 0)),
                    'quote': float(pair.get('liquidity', {}).get('quote', 0)),
                },
                'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                'txns_24h': pair.get('txns', {}).get('h24', {}),
                'created_at': pair.get('pairCreatedAt', 0),
            }
        except Exception as e:
            logger.error(f"Failed to extract pair data: {e}")
            return {}