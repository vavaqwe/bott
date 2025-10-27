import asyncio
import aiohttp
from typing import Optional
from utils import setup_logging
from config import config

logger = setup_logging(__name__)

class TelegramAdmin:
    """Telegram bot for notifications and admin commands"""
    
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        logger.info("Telegram Admin initialized")
    
    async def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Send message to Telegram chat"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/sendMessage"
                payload = {
                    'chat_id': self.chat_id,
                    'text': text,
                    'parse_mode': parse_mode,
                    'disable_web_page_preview': True
                }
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.debug(f"Message sent to Telegram")
                        return True
                    else:
                        logger.error(f"Failed to send message: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_message_sync(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Synchronous wrapper for send_message"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(self.send_message(text, parse_mode))
                new_loop.close()
                return result
            else:
                return loop.run_until_complete(self.send_message(text, parse_mode))
        except Exception as e:
            logger.error(f"Error in sync send: {e}")
            return False
    
    async def send_signal_notification(self, signal_data: dict):
        """Send trading signal notification"""
        try:
            base_token = signal_data.get('base_token', {})
            spread = signal_data.get('spread', 0)
            action = signal_data.get('action', 'skip')
            dex_price = signal_data.get('dex_price', 0)
            cex_price = signal_data.get('cex_price', 0)
            liquidity = signal_data.get('liquidity', 0)
            volume = signal_data.get('volume_24h', 0)
            
            # Determine emoji based on action
            emoji = "🔔" if action == 'notify' else "✅" if action == 'execute' else "⚠️"
            
            message = f"{emoji} <b>Trading Signal</b>\n\n"
            message += f"<b>Token:</b> {base_token.get('symbol', 'Unknown')} ({base_token.get('name', 'Unknown')})\n"
            message += f"<b>Chain:</b> {signal_data.get('chain', 'Unknown')}\n"
            message += f"<b>DEX:</b> {signal_data.get('dex', 'Unknown')}\n\n"
            message += f"<b>Spread:</b> {spread:.2f}%\n"
            message += f"<b>DEX Price:</b> ${dex_price:.8f}\n"
            message += f"<b>CEX Price:</b> ${cex_price:.8f}\n\n"
            message += f"<b>Liquidity:</b> ${liquidity:,.0f}\n"
            message += f"<b>Volume 24h:</b> ${volume:,.0f}\n\n"
            message += f"<b>Action:</b> {action.upper()}\n"
            
            if signal_data.get('reasons'):
                message += f"<b>Reasons:</b> {', '.join(signal_data['reasons'])}\n"
            
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending signal notification: {e}")
    
    async def send_trade_notification(self, trade_data: dict):
        """Send trade execution notification"""
        try:
            message = f"✅ <b>Trade Executed</b>\n\n"
            message += f"<b>Symbol:</b> {trade_data.get('symbol', 'Unknown')}\n"
            message += f"<b>Side:</b> {trade_data.get('side', 'Unknown')}\n"
            message += f"<b>Quantity:</b> {trade_data.get('quantity', 0)}\n"
            message += f"<b>Price:</b> ${trade_data.get('price', 0):.8f}\n"
            message += f"<b>Order ID:</b> {trade_data.get('order_id', 'N/A')}\n"
            
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending trade notification: {e}")
    
    async def send_heartbeat(self, stats: dict):
        """Send heartbeat status"""
        try:
            message = f"💓 <b>Bot Heartbeat</b>\n\n"
            message += f"<b>Uptime:</b> {stats.get('uptime', 'Unknown')}\n"
            message += f"<b>Signals processed:</b> {stats.get('signals_processed', 0)}\n"
            message += f"<b>Trades executed:</b> {stats.get('trades_executed', 0)}\n"
            message += f"<b>Active chains:</b> {', '.join(stats.get('active_chains', []))}\n"
            message += f"<b>Last block:</b> {stats.get('last_block', 'N/A')}\n"
            
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
    
    async def send_error_notification(self, error_message: str):
        """Send error notification"""
        try:
            message = f"🚨 <b>Error Alert</b>\n\n"
            message += f"<code>{error_message}</code>\n"
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")