from typing import Dict, Optional
from utils import setup_logging, calculate_spread
from config import config

logger = setup_logging(__name__)

class SignalVerification:
    """Verify and validate trading signals"""
    
    def __init__(self):
        self.min_spread = config.MIN_SPREAD_PERCENT
        self.max_spread = config.MAX_SPREAD_PERCENT
        self.min_liquidity = config.MIN_LIQUIDITY_USD
        self.min_volume = config.MIN_VOLUME_24H_USD
        logger.info(f"Signal verification initialized - Spread: {self.min_spread}%-{self.max_spread}%, Min Liquidity: ${self.min_liquidity}, Min Volume: ${self.min_volume}")
    
    def verify_signal(self, dex_data: Dict, xt_data: Optional[Dict]) -> Dict:
        """Verify if signal meets all criteria"""
        result = {
            'valid': False,
            'action': 'skip',
            'reasons': [],
            'spread': 0,
            'dex_price': 0,
            'cex_price': 0,
        }
        
        try:
            # Extract DEX price and liquidity
            dex_price = dex_data.get('price_usd', 0)
            liquidity_usd = dex_data.get('liquidity', {}).get('usd', 0)
            volume_24h = dex_data.get('volume_24h', 0)
            
            result['dex_price'] = dex_price
            
            # Check if token exists on XT
            if not xt_data:
                result['reasons'].append('Token not listed on XT')
                return result
            
            # Extract CEX price
            cex_price = float(xt_data.get('price', 0))
            result['cex_price'] = cex_price
            
            if cex_price == 0 or dex_price == 0:
                result['reasons'].append('Invalid price data')
                return result
            
            # Calculate spread
            spread = calculate_spread(dex_price, cex_price)
            result['spread'] = spread
            
            # Check spread range
            if spread < self.min_spread:
                result['reasons'].append(f'Spread too low: {spread:.2f}% < {self.min_spread}%')
                return result
            
            if spread > self.max_spread:
                result['reasons'].append(f'Spread too high: {spread:.2f}% > {self.max_spread}%')
                result['action'] = 'notify'  # Notify but don't execute
                return result
            
            # Check liquidity
            if liquidity_usd < self.min_liquidity:
                result['reasons'].append(f'Liquidity too low: ${liquidity_usd:.0f} < ${self.min_liquidity}')
                return result
            
            # Check volume
            if volume_24h < self.min_volume:
                result['reasons'].append(f'Volume too low: ${volume_24h:.0f} < ${self.min_volume}')
                return result
            
            # All checks passed
            result['valid'] = True
            result['action'] = 'execute' if config.ALLOW_LIVE_TRADING else 'notify'
            result['reasons'].append('All criteria met')
            
        except Exception as e:
            logger.error(f"Error verifying signal: {e}")
            result['reasons'].append(f'Verification error: {str(e)}')
        
        return result
    
    def should_execute_trade(self, verification_result: Dict) -> bool:
        """Determine if trade should be executed"""
        return (
            verification_result.get('valid', False) and 
            verification_result.get('action') == 'execute' and
            config.ALLOW_LIVE_TRADING
        )