import logging
import time
from functools import wraps
from typing import Optional
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def setup_logging(name: str) -> logging.Logger:
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(name)

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying functions on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                        time.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"All {max_retries} attempts failed")
            raise last_exception
        return wrapper
    return decorator

def normalize_address(address: str) -> str:
    """Normalize blockchain address to lowercase"""
    if not address:
        return ""
    return address.lower().strip()

def format_number(num: float, decimals: int = 2) -> str:
    """Format number with proper decimals"""
    if num >= 1_000_000:
        return f"${num/1_000_000:.{decimals}f}M"
    elif num >= 1_000:
        return f"${num/1_000:.{decimals}f}K"
    else:
        return f"${num:.{decimals}f}"

def calculate_spread(dex_price: float, cex_price: float) -> float:
    """Calculate spread percentage between DEX and CEX"""
    if cex_price == 0:
        return 0
    spread = ((dex_price - cex_price) / cex_price) * 100
    return abs(spread)

def save_to_json(data: dict, filename: str):
    """Save data to JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Data saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save data to {filename}: {e}")

def load_from_json(filename: str) -> Optional[dict]:
    """Load data from JSON file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"File {filename} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to load data from {filename}: {e}")
        return None

def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()

def measure_latency(func):
    """Decorator to measure function execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start_time
        logger.debug(f"{func.__name__} latency: {latency:.3f}s")
        return result
    return wrapper