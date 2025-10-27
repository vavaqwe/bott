import requests
import asyncio
import aiohttp
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
        self.rate_limit_delay = 0.5  # 0.5 second between requests for faster scanning
        self.chains = ['ethereum', 'bsc', 'polygon', 'arbitrum', 'base', 'solana']
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
            # Use multiple strategies to get more signals
            all_pairs = []

            # Strategy 1: Get pairs from multiple chains
            for chain in ['ethereum', 'bsc', 'polygon']:
                try:
                    chain_pairs = self._get_chain_latest_pairs(chain)
                    all_pairs.extend(chain_pairs)
                except Exception as e:
                    logger.error(f"Error getting pairs from {chain}: {e}")

            # Strategy 2: Get trending pairs
            trending = self._get_trending_pairs()
            all_pairs.extend(trending)

            # Remove duplicates based on pair_address
            seen = set()
            unique_pairs = []
            for pair in all_pairs:
                pair_addr = pair.get('pairAddress', '')
                if pair_addr and pair_addr not in seen:
                    seen.add(pair_addr)
                    unique_pairs.append(pair)

            logger.info(f"Fetched {len(unique_pairs)} unique latest pairs")
            return unique_pairs[:100]  # Increased limit to 100
        except Exception as e:
            logger.error(f"Failed to get latest pairs: {e}")
            return self._get_trending_pairs()

    def _get_chain_latest_pairs(self, chain: str) -> List[Dict]:
        """Get latest pairs from specific chain"""
        try:
            # Use search endpoint with popular tokens for each chain
            popular_tokens = {
                'ethereum': ['PEPE', 'SHIB', 'WOJAK'],
                'bsc': ['CAKE', 'BABY', 'SAFEMOON'],
                'polygon': ['MATIC', 'QUICK', 'GHST']
            }

            chain_tokens = popular_tokens.get(chain, ['ETH'])
            all_pairs = []

            for token in chain_tokens:
                try:
                    self._rate_limit()
                    pairs = self.search_pairs(f"{token}")
                    if pairs:
                        # Filter to only this chain
                        filtered = [p for p in pairs if p.get('chainId', '').lower() == chain.lower()]
                        all_pairs.extend(filtered[:5])
                except Exception as e:
                    logger.debug(f"Error searching {token} on {chain}: {e}")
                    continue

            logger.info(f"Got {len(all_pairs)} pairs from {chain}")
            return all_pairs[:20]
        except Exception as e:
            logger.error(f"Error getting {chain} pairs: {e}")
            return []
    
    def _get_trending_pairs(self) -> List[Dict]:
        """Fallback method to get trending pairs"""
        try:
            # Search for popular and trending tokens
            popular_tokens = [
                'PEPE', 'SHIB', 'DOGE', 'FLOKI', 'WOJAK',
                'BONK', 'WIF', 'MEME', 'TRUMP', 'PEPE2',
                'AIDOGE', 'TURBO', 'LADYS', 'CHAD', 'SMOL'
            ]
            pairs = []
            for token in popular_tokens:
                try:
                    search_results = self.search_pairs(token)
                    if search_results:
                        # Sort by liquidity and volume
                        sorted_results = sorted(
                            search_results,
                            key=lambda x: float(x.get('liquidity', {}).get('usd', 0)) + float(x.get('volume', {}).get('h24', 0)),
                            reverse=True
                        )
                        pairs.extend(sorted_results[:3])
                except Exception as e:
                    logger.error(f"Error searching {token}: {e}")
                    continue
            return pairs[:50]
        except Exception as e:
            logger.error(f"Failed to get trending pairs: {e}")
            return []

    async def get_latest_pairs_async(self) -> List[Dict]:
        """Async version to get pairs from multiple sources simultaneously"""
        try:
            tasks = []

            # Create tasks for each chain
            for chain in ['ethereum', 'bsc', 'polygon', 'base']:
                tasks.append(self._fetch_chain_pairs_async(chain))

            # Fetch all in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_pairs = []
            for result in results:
                if isinstance(result, list):
                    all_pairs.extend(result)

            # Remove duplicates
            seen = set()
            unique_pairs = []
            for pair in all_pairs:
                pair_addr = pair.get('pairAddress', '')
                if pair_addr and pair_addr not in seen:
                    seen.add(pair_addr)
                    unique_pairs.append(pair)

            logger.info(f"Async fetched {len(unique_pairs)} unique pairs")
            return unique_pairs[:100]
        except Exception as e:
            logger.error(f"Error in async fetch: {e}")
            return []

    async def _fetch_chain_pairs_async(self, chain: str) -> List[Dict]:
        """Async fetch pairs from chain"""
        try:
            # Use search API for popular tokens
            popular_tokens = {
                'ethereum': ['PEPE', 'SHIB'],
                'bsc': ['CAKE', 'BABY'],
                'polygon': ['MATIC'],
                'base': ['BRETT', 'DEGEN']
            }

            chain_tokens = popular_tokens.get(chain, ['ETH'])
            all_pairs = []

            async with aiohttp.ClientSession() as session:
                for token in chain_tokens:
                    try:
                        url = f"https://api.dexscreener.com/latest/dex/search"
                        params = {'q': token}
                        async with session.get(url, params=params, timeout=10) as response:
                            if response.status == 200:
                                data = await response.json()
                                pairs = data.get('pairs', [])
                                # Filter to this chain
                                filtered = [p for p in pairs if p.get('chainId', '').lower() == chain.lower()]
                                all_pairs.extend(filtered[:5])
                        await asyncio.sleep(0.5)  # Rate limiting
                    except Exception as e:
                        logger.debug(f"Error fetching {token} on {chain}: {e}")
                        continue

            return all_pairs[:25]
        except Exception as e:
            logger.error(f"Error fetching {chain} async: {e}")
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