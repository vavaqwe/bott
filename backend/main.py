#!/usr/bin/env python3
"""
Trinkenbot Enhanced - Main Entry Point
Automated trading bot for DEX arbitrage with XT.com integration
"""

import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from bot import TradingBot
from utils import setup_logging
from config import config

logger = setup_logging(__name__)

def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("Trinkenbot Enhanced - Starting")
    logger.info("="*60)
    logger.info(f"Live Trading: {'ENABLED' if config.ALLOW_LIVE_TRADING else 'DISABLED'}")
    logger.info(f"Spread Range: {config.MIN_SPREAD_PERCENT}% - {config.MAX_SPREAD_PERCENT}%")
    logger.info(f"Min Liquidity: ${config.MIN_LIQUIDITY_USD:,.0f}")
    logger.info(f"Min Volume 24h: ${config.MIN_VOLUME_24H_USD:,.0f}")
    logger.info("="*60)
    
    try:
        # Initialize and start bot
        bot = TradingBot()
        bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()