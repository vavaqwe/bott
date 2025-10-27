from web3 import Web3
from typing import Optional, Dict, List
from utils import setup_logging, retry_on_failure, normalize_address
from config import config
import time

logger = setup_logging(__name__)

class BlockchainClient:
    """Client for interacting with multiple blockchains"""
    
    def __init__(self):
        self.chains = {}
        self._initialize_chains()
        self.last_blocks = {}
        logger.info("Blockchain Client initialized")
    
    def _initialize_chains(self):
        """Initialize Web3 connections for each chain"""
        chain_configs = [
            ('ethereum', config.ETH_RPC_URL),
            ('bsc', config.BSC_RPC_URL),
        ]
        
        for chain_name, rpc_url in chain_configs:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))
                if w3.is_connected():
                    self.chains[chain_name] = w3
                    self.last_blocks[chain_name] = 0
                    logger.info(f"Connected to {chain_name} at {rpc_url}")
                else:
                    logger.error(f"Failed to connect to {chain_name}")
            except Exception as e:
                logger.error(f"Error initializing {chain_name}: {e}")
    
    def reconnect_if_needed(self, chain: str):
        """Reconnect to chain if connection is lost"""
        try:
            if chain not in self.chains:
                return False
            
            w3 = self.chains[chain]
            if not w3.is_connected():
                logger.warning(f"Connection lost to {chain}, reconnecting...")
                rpc_url = config.ETH_RPC_URL if chain == 'ethereum' else config.BSC_RPC_URL
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))
                if w3.is_connected():
                    self.chains[chain] = w3
                    logger.info(f"Reconnected to {chain}")
                    return True
                else:
                    logger.error(f"Failed to reconnect to {chain}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error reconnecting to {chain}: {e}")
            return False
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def get_latest_block(self, chain: str) -> Optional[int]:
        """Get the latest block number"""
        try:
            if chain not in self.chains:
                return None
            
            self.reconnect_if_needed(chain)
            w3 = self.chains[chain]
            block_number = w3.eth.block_number
            logger.debug(f"Latest block on {chain}: {block_number}")
            return block_number
        except Exception as e:
            logger.error(f"Failed to get latest block for {chain}: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def get_block(self, chain: str, block_number: int) -> Optional[Dict]:
        """Get block data"""
        try:
            if chain not in self.chains:
                return None
            
            self.reconnect_if_needed(chain)
            w3 = self.chains[chain]
            block = w3.eth.get_block(block_number, full_transactions=True)
            logger.debug(f"Fetched block {block_number} from {chain} with {len(block.transactions)} txs")
            return dict(block)
        except Exception as e:
            logger.error(f"Failed to get block {block_number} for {chain}: {e}")
            return None
    
    @retry_on_failure(max_retries=3, delay=2.0)
    def get_transaction(self, chain: str, tx_hash: str) -> Optional[Dict]:
        """Get transaction data"""
        try:
            if chain not in self.chains:
                return None
            
            self.reconnect_if_needed(chain)
            w3 = self.chains[chain]
            tx = w3.eth.get_transaction(tx_hash)
            return dict(tx)
        except Exception as e:
            logger.error(f"Failed to get transaction {tx_hash} for {chain}: {e}")
            return None
    
    def parse_swap_events(self, block_data: Dict, chain: str) -> List[Dict]:
        """Parse swap/liquidity events from block transactions"""
        events = []
        
        try:
            transactions = block_data.get('transactions', [])
            
            # Known DEX router signatures (simplified)
            swap_signatures = [
                '0x38ed1739',  # swapExactTokensForTokens
                '0x8803dbee',  # swapTokensForExactTokens
                '0x7ff36ab5',  # swapExactETHForTokens
                '0x18cbafe5',  # swapExactTokensForETH
                '0xe8e33700',  # addLiquidity
                '0xf305d719',  # addLiquidityETH
            ]
            
            for tx in transactions:
                if not tx or not isinstance(tx, dict):
                    continue
                
                input_data = tx.get('input', '')
                if not input_data or len(input_data) < 10:
                    continue
                
                method_sig = input_data[:10]
                
                if method_sig in swap_signatures:
                    event = {
                        'chain': chain,
                        'tx_hash': tx.get('hash', '').hex() if hasattr(tx.get('hash', ''), 'hex') else str(tx.get('hash', '')),
                        'from': normalize_address(tx.get('from', '')),
                        'to': normalize_address(tx.get('to', '')),
                        'value': tx.get('value', 0),
                        'block_number': block_data.get('number', 0),
                        'timestamp': block_data.get('timestamp', 0),
                        'method': method_sig,
                    }
                    events.append(event)
            
            if events:
                logger.info(f"Found {len(events)} swap events in block {block_data.get('number', 0)} on {chain}")
        
        except Exception as e:
            logger.error(f"Error parsing swap events: {e}")
        
        return events
    
    def monitor_new_blocks(self, chain: str) -> List[Dict]:
        """Monitor for new blocks and return events"""
        events = []
        
        try:
            latest_block = self.get_latest_block(chain)
            if not latest_block:
                return events
            
            last_processed = self.last_blocks.get(chain, latest_block - 1)
            
            # Process new blocks
            for block_num in range(last_processed + 1, latest_block + 1):
                block_data = self.get_block(chain, block_num)
                if block_data:
                    block_events = self.parse_swap_events(block_data, chain)
                    events.extend(block_events)
                    self.last_blocks[chain] = block_num
                
                # Avoid processing too many blocks at once
                if len(events) > 100:
                    break
        
        except Exception as e:
            logger.error(f"Error monitoring blocks for {chain}: {e}")
        
        return events