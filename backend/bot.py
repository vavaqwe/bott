import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List
from utils import setup_logging, save_to_json, load_from_json
from config import config
from blockchain_client import BlockchainClient
from dex_client import DexClient
from xt_client import XTClient
from signal_verification import SignalVerification
from telegram_admin import TelegramAdmin

logger = setup_logging(__name__)

class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        self.blockchain_client = BlockchainClient()
        self.dex_client = DexClient()
        self.xt_client = XTClient()
        self.signal_verification = SignalVerification()
        self.telegram = TelegramAdmin()
        
        self.running = False
        self.start_time = time.time()
        self.stats = {
            'signals_processed': 0,
            'signals_valid': 0,
            'trades_executed': 0,
            'last_heartbeat': time.time(),
        }
        
        # Load previous state
        self.positions = load_from_json('positions.json') or {}
        self.trades = load_from_json('trades.json') or []
        
        logger.info("Trading Bot initialized")
    
    async def process_dex_pair(self, pair_data: Dict) -> bool:
        """Process a DEX pair and check for arbitrage opportunity"""
        try:
            # Extract pair info
            base_token = pair_data.get('base_token', {})
            token_address = base_token.get('address', '')
            token_symbol = base_token.get('symbol', '')
            chain = pair_data.get('chain', '')
            
            if not token_address or not token_symbol:
                return False
            
            # Try to find corresponding symbol on XT
            xt_symbol = self.xt_client.find_symbol_by_address(token_address)
            
            if not xt_symbol:
                # Try with symbol name
                xt_symbol = f"{token_symbol.upper()}_USDT"
            
            # Get XT ticker
            xt_ticker = self.xt_client.get_ticker(xt_symbol)
            
            # Verify signal
            verification = self.signal_verification.verify_signal(pair_data, xt_ticker)
            
            self.stats['signals_processed'] += 1
            
            # Prepare signal data
            signal_data = {
                'chain': chain,
                'dex': pair_data.get('dex', ''),
                'base_token': base_token,
                'spread': verification.get('spread', 0),
                'dex_price': verification.get('dex_price', 0),
                'cex_price': verification.get('cex_price', 0),
                'liquidity': pair_data.get('liquidity', {}).get('usd', 0),
                'volume_24h': pair_data.get('volume_24h', 0),
                'action': verification.get('action', 'skip'),
                'reasons': verification.get('reasons', []),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            # If valid, send notification
            if verification.get('valid') or verification.get('action') == 'notify':
                self.stats['signals_valid'] += 1
                await self.telegram.send_signal_notification(signal_data)
                
                # Execute trade if conditions are met
                if self.signal_verification.should_execute_trade(verification):
                    await self.execute_trade(xt_symbol, signal_data)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing DEX pair: {e}")
            return False
    
    async def execute_trade(self, symbol: str, signal_data: Dict):
        """Execute trade on XT exchange"""
        try:
            if not config.ALLOW_LIVE_TRADING:
                logger.info(f"Simulated trade for {symbol}")
                return
            
            # Get orderbook to determine trade size
            orderbook = self.xt_client.get_orderbook(symbol)
            
            if not orderbook:
                logger.warning(f"No orderbook data for {symbol}")
                return
            
            # Calculate trade quantity (simplified)
            # In production, use more sophisticated position sizing
            quantity = 100  # Example fixed quantity
            
            # Determine side based on spread direction
            dex_price = signal_data.get('dex_price', 0)
            cex_price = signal_data.get('cex_price', 0)
            side = 'BUY' if dex_price < cex_price else 'SELL'
            
            # Place order
            order = self.xt_client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity
            )
            
            if order:
                self.stats['trades_executed'] += 1
                
                # Record trade
                trade_record = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'order_id': order.get('orderId', 'N/A'),
                    'signal_data': signal_data,
                }
                self.trades.append(trade_record)
                save_to_json(self.trades, 'trades.json')
                
                # Send notification
                await self.telegram.send_trade_notification({
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': cex_price,
                    'order_id': order.get('orderId', 'N/A'),
                })
                
                logger.info(f"Trade executed: {symbol} {side} {quantity}")
        
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            await self.telegram.send_error_notification(f"Trade execution failed: {str(e)}")
    
    async def scan_dex_pairs(self):
        """Scan DEX for new pairs and opportunities"""
        try:
            # Get latest pairs from DEXScreener
            pairs = self.dex_client.get_latest_pairs()
            
            logger.info(f"Scanning {len(pairs)} DEX pairs...")
            
            if not pairs:
                logger.warning("No pairs found from DEXScreener, trying alternative method...")
                # Try to get some specific token pairs
                await self._scan_specific_tokens()
                return
            
            # Process pairs
            tasks = []
            for pair in pairs[:30]:  # Limit to 30 pairs per scan to avoid rate limits
                # Check if pair is already dict or needs extraction
                if isinstance(pair, dict):
                    # Check if it's already extracted
                    if 'base_token' in pair:
                        pair_data = pair
                    else:
                        pair_data = self.dex_client.extract_pair_data(pair)
                else:
                    continue
                    
                if pair_data and pair_data.get('base_token'):
                    tasks.append(self.process_dex_pair(pair_data))
            
            # Process in batches to avoid overwhelming APIs
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in results if r and not isinstance(r, Exception))
                logger.info(f"Processed {successful} pairs successfully")
        
        except Exception as e:
            logger.error(f"Error scanning DEX pairs: {e}")
    
    async def _scan_specific_tokens(self):
        """Scan specific popular tokens as fallback"""
        try:
            # Popular token addresses on Ethereum
            popular_tokens = {
                'ethereum': [
                    '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE',  # SHIB
                    '0x6982508145454Ce325dDbE47a25d4ec3d2311933',  # PEPE
                ]
            }
            
            for chain, addresses in popular_tokens.items():
                for address in addresses:
                    try:
                        pair_info = self.dex_client.get_token_info(chain, address)
                        if pair_info:
                            pair_data = self.dex_client.extract_pair_data(pair_info)
                            if pair_data:
                                await self.process_dex_pair(pair_data)
                        await asyncio.sleep(2)  # Rate limiting
                    except Exception as e:
                        logger.error(f"Error scanning token {address}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error in specific token scanning: {e}")
    
    async def monitor_blockchains(self):
        """Monitor blockchain for new swap events"""
        try:
            for chain in ['ethereum', 'bsc']:
                events = self.blockchain_client.monitor_new_blocks(chain)
                
                if events:
                    logger.info(f"Found {len(events)} events on {chain}")
                    
                    # For each event, try to get DEX data
                    for event in events[:20]:  # Limit processing
                        # Extract token addresses from event
                        # This is simplified - in production, decode the transaction input
                        pass
        
        except Exception as e:
            logger.error(f"Error monitoring blockchains: {e}")
    
    async def send_heartbeat(self):
        """Send periodic heartbeat"""
        try:
            uptime = time.time() - self.start_time
            uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"
            
            stats = {
                'uptime': uptime_str,
                'signals_processed': self.stats['signals_processed'],
                'trades_executed': self.stats['trades_executed'],
                'active_chains': list(self.blockchain_client.chains.keys()),
                'last_block': max(self.blockchain_client.last_blocks.values()) if self.blockchain_client.last_blocks else 0,
            }
            
            await self.telegram.send_heartbeat(stats)
            self.stats['last_heartbeat'] = time.time()
            
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
    
    async def main_loop(self):
        """Main bot loop"""
        logger.info("Starting main bot loop...")
        self.running = True
        
        # Send startup message
        await self.telegram.send_message("🚀 <b>Trading Bot Started</b>\n\nMonitoring DEX and blockchain for arbitrage opportunities...")
        
        while self.running:
            try:
                # Scan DEX pairs
                await self.scan_dex_pairs()
                
                # Monitor blockchains (optional, can be heavy)
                # await self.monitor_blockchains()
                
                # Send heartbeat if needed
                if time.time() - self.stats['last_heartbeat'] > config.HEARTBEAT_INTERVAL:
                    await self.send_heartbeat()
                
                # Wait before next iteration
                await asyncio.sleep(10)  # Scan every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await self.telegram.send_error_notification(f"Main loop error: {str(e)}")
                await asyncio.sleep(30)  # Wait longer on error
    
    def start(self):
        """Start the bot"""
        try:
            asyncio.run(self.main_loop())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise