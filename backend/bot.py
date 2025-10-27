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
            'last_signal_time': 0,
            'errors_count': 0,
        }

        # Load previous state
        self.positions = load_from_json('positions.json') or {}
        self.trades = load_from_json('trades.json') or []

        # Register Telegram commands
        self._register_commands()

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
            
            # If no XT ticker, skip (token not listed)
            if not xt_ticker:
                logger.debug(f"Token {token_symbol} not available on XT, skipping")
                self.stats['signals_processed'] += 1
                return False
            
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
                logger.info(f"✓ Valid signal: {token_symbol} - Spread: {verification.get('spread', 0):.2f}%")
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
            # Use async version to fetch from multiple chains simultaneously
            pairs = await self.dex_client.get_latest_pairs_async()

            if not pairs or len(pairs) == 0:
                # Fallback to sync method
                pairs = self.dex_client.get_latest_pairs()

            logger.info(f"Scanning {len(pairs)} DEX pairs...")

            if not pairs:
                logger.warning("No pairs found from DEXScreener, trying alternative method...")
                # Try to get some specific token pairs
                await self._scan_specific_tokens()
                return

            # Process pairs in batches to avoid rate limits
            batch_size = 20
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i:i+batch_size]
                tasks = []

                for pair in batch:
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

                # Process batch
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    successful = sum(1 for r in results if r and not isinstance(r, Exception))
                    logger.info(f"Batch {i//batch_size + 1}: Processed {successful}/{len(tasks)} pairs successfully")

                # Small delay between batches
                if i + batch_size < len(pairs):
                    await asyncio.sleep(1)

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
    
    def _register_commands(self):
        """Register Telegram bot commands"""
        self.telegram.register_command('/start', self._cmd_start)
        self.telegram.register_command('/status', self._cmd_status)
        self.telegram.register_command('/balance', self._cmd_balance)
        self.telegram.register_command('/stats', self._cmd_stats)
        self.telegram.register_command('/settings', self._cmd_settings)
        self.telegram.register_command('/stop', self._cmd_stop)
        self.telegram.register_command('/help', self._cmd_help)
        # Callback handlers for buttons
        self.telegram.register_command('toggle_trading', self._callback_toggle_trading)
        self.telegram.register_command('show_balance', self._callback_show_balance)

    async def _cmd_start(self, message: Dict):
        """Handle /start command"""
        welcome_msg = (
            "🚀 <b>Welcome to Trinkenbot Enhanced!</b>\n\n"
            "I'm your automated DEX arbitrage trading bot.\n\n"
            "<b>Commands:</b>\n"
            "/status - Bot status\n"
            "/balance - Account balance\n"
            "/stats - Trading statistics\n"
            "/settings - Bot settings\n"
            "/help - Show help\n\n"
            "Bot is monitoring DEX markets for arbitrage opportunities on XT.com!"
        )
        keyboard = {
            'inline_keyboard': [
                [{'text': '📊 Status', 'callback_data': '/status'},
                 {'text': '💰 Balance', 'callback_data': 'show_balance'}],
                [{'text': '⚙️ Settings', 'callback_data': '/settings'}]
            ]
        }
        await self.telegram.send_message(welcome_msg, reply_markup=keyboard)

    async def _cmd_status(self, message: Dict):
        """Handle /status command"""
        uptime = time.time() - self.start_time
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"

        status_msg = (
            "🟢 <b>Bot Status</b>\n\n"
            f"<b>Status:</b> {'Running' if self.running else 'Stopped'}\n"
            f"<b>Uptime:</b> {uptime_str}\n"
            f"<b>Live Trading:</b> {'ON' if config.ALLOW_LIVE_TRADING else 'OFF'}\n\n"
            f"<b>Signals Processed:</b> {self.stats['signals_processed']}\n"
            f"<b>Valid Signals:</b> {self.stats['signals_valid']}\n"
            f"<b>Trades Executed:</b> {self.stats['trades_executed']}\n"
            f"<b>Errors:</b> {self.stats['errors_count']}"
        )
        await self.telegram.send_message(status_msg)

    async def _cmd_balance(self, message: Dict):
        """Handle /balance command"""
        try:
            balance = self.xt_client.get_balance()
            if balance:
                assets = balance.get('assets', [])
                msg = "💰 <b>Account Balance</b>\n\n"
                for asset in assets[:10]:  # Show top 10
                    free = float(asset.get('free', 0))
                    if free > 0:
                        msg += f"<b>{asset.get('asset', 'N/A')}:</b> {free:.4f}\n"
            else:
                msg = "⚠️ Failed to fetch balance"
        except Exception as e:
            msg = f"⚠️ Error: {str(e)}"
        await self.telegram.send_message(msg)

    async def _cmd_stats(self, message: Dict):
        """Handle /stats command"""
        trades_count = len(self.trades)
        positions_count = len(self.positions)

        msg = (
            "📊 <b>Trading Statistics</b>\n\n"
            f"<b>Total Trades:</b> {trades_count}\n"
            f"<b>Open Positions:</b> {positions_count}\n"
            f"<b>Signals Processed:</b> {self.stats['signals_processed']}\n"
            f"<b>Valid Signals:</b> {self.stats['signals_valid']}\n"
        )

        if trades_count > 0:
            recent_trades = self.trades[-5:]
            msg += "\n<b>Recent Trades:</b>\n"
            for trade in recent_trades:
                symbol = trade.get('symbol', 'N/A')
                side = trade.get('side', 'N/A')
                qty = trade.get('quantity', 0)
                msg += f"• {symbol} {side} {qty}\n"

        await self.telegram.send_message(msg)

    async def _cmd_settings(self, message: Dict):
        """Handle /settings command"""
        msg = (
            "⚙️ <b>Bot Settings</b>\n\n"
            f"<b>Live Trading:</b> {'ON' if config.ALLOW_LIVE_TRADING else 'OFF'}\n"
            f"<b>Min Spread:</b> {config.MIN_SPREAD_PERCENT}%\n"
            f"<b>Max Spread:</b> {config.MAX_SPREAD_PERCENT}%\n"
            f"<b>Min Liquidity:</b> ${config.MIN_LIQUIDITY_USD:,.0f}\n"
            f"<b>Min Volume 24h:</b> ${config.MIN_VOLUME_24H_USD:,.0f}\n"
        )
        keyboard = {
            'inline_keyboard': [
                [{'text': f"{'Disable' if config.ALLOW_LIVE_TRADING else 'Enable'} Trading",
                  'callback_data': 'toggle_trading'}]
            ]
        }
        await self.telegram.send_message(msg, reply_markup=keyboard)

    async def _cmd_stop(self, message: Dict):
        """Handle /stop command"""
        self.running = False
        await self.telegram.send_message("🛑 Bot is stopping...")

    async def _cmd_help(self, message: Dict):
        """Handle /help command"""
        help_msg = (
            "📚 <b>Help - Trinkenbot Enhanced</b>\n\n"
            "<b>Available Commands:</b>\n"
            "/start - Initialize bot\n"
            "/status - Show bot status\n"
            "/balance - View account balance\n"
            "/stats - Trading statistics\n"
            "/settings - View/change settings\n"
            "/stop - Stop the bot\n"
            "/help - Show this help\n\n"
            "<b>About:</b>\n"
            "This bot monitors DEX markets and executes arbitrage trades on XT.com when profitable opportunities are found.\n\n"
            f"<b>Current Settings:</b>\n"
            f"• Spread: {config.MIN_SPREAD_PERCENT}%-{config.MAX_SPREAD_PERCENT}%\n"
            f"• Min Liquidity: ${config.MIN_LIQUIDITY_USD:,.0f}"
        )
        await self.telegram.send_message(help_msg)

    async def _callback_toggle_trading(self, callback: Dict):
        """Handle toggle trading button"""
        config.ALLOW_LIVE_TRADING = not config.ALLOW_LIVE_TRADING
        status = 'enabled' if config.ALLOW_LIVE_TRADING else 'disabled'
        await self.telegram.send_message(f"✅ Live trading {status}")

    async def _callback_show_balance(self, callback: Dict):
        """Handle show balance button"""
        await self._cmd_balance(callback)

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

        # Start Telegram polling
        self.telegram.start_polling()

        # Send startup message
        startup_msg = (
            "🚀 <b>Trading Bot Started</b>\n\n"
            "Monitoring DEX for arbitrage opportunities...\n\n"
            f"<b>Settings:</b>\n"
            f"• Spread: {config.MIN_SPREAD_PERCENT}%-{config.MAX_SPREAD_PERCENT}%\n"
            f"• Min Liquidity: ${config.MIN_LIQUIDITY_USD:,.0f}\n"
            f"• Live Trading: {'ON' if config.ALLOW_LIVE_TRADING else 'OFF'}"
        )
        await self.telegram.send_message(startup_msg)

        scan_interval = 5  # Scan every 5 seconds for more signals

        while self.running:
            try:
                # Scan DEX pairs
                await self.scan_dex_pairs()

                # Monitor blockchains (optional, can be heavy)
                # await self.monitor_blockchains()

                # Send heartbeat if needed
                if time.time() - self.stats['last_heartbeat'] > config.HEARTBEAT_INTERVAL:
                    await self.send_heartbeat()

                # Save stats to file for dashboard
                save_to_json(self.stats, 'bot_stats.json')

                # Wait before next iteration
                await asyncio.sleep(scan_interval)

            except KeyboardInterrupt:
                logger.info("Stopping bot...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.stats['errors_count'] += 1
                await self.telegram.send_error_notification(f"Main loop error: {str(e)}")
                await asyncio.sleep(30)  # Wait longer on error

        # Cleanup
        self.telegram.stop_polling()
        await self.telegram.send_message("🛑 <b>Bot Stopped</b>")
    
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