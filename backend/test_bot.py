#!/usr/bin/env python3
"""
Test script to verify bot configuration and API connectivity
"""

import sys
import os

print("="*60)
print("Trinkenbot Enhanced - Configuration Test")
print("="*60)

# Test 1: Check environment variables
print("\n1. Checking environment variables...")
env_file = ".env"
if os.path.exists(env_file):
    print(f"✓ {env_file} exists")
    with open(env_file) as f:
        lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('#')]
    print(f"✓ Found {len(lines)} configuration entries")

    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID',
        'XT_ACCOUNT_2_API_KEY',
        'XT_ACCOUNT_2_API_SECRET'
    ]

    # Load .env manually
    env_vars = {}
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()

    for var in required_vars:
        if var in env_vars and env_vars[var]:
            print(f"✓ {var} is set")
        else:
            print(f"✗ {var} is missing or empty!")
else:
    print(f"✗ {env_file} not found!")
    sys.exit(1)

# Test 2: Check Python modules
print("\n2. Checking Python modules...")
required_modules = [
    'requests',
    'aiohttp',
    'web3',
    'dotenv'
]

missing_modules = []
for module in required_modules:
    try:
        __import__(module if module != 'dotenv' else 'dotenv')
        print(f"✓ {module} is installed")
    except ImportError:
        print(f"✗ {module} is NOT installed!")
        missing_modules.append(module)

if missing_modules:
    print(f"\nPlease install missing modules: pip install {' '.join(missing_modules)}")
    sys.exit(1)

# Test 3: Test XT API connectivity
print("\n3. Testing XT.com API connectivity...")
try:
    import requests

    api_key = env_vars.get('XT_ACCOUNT_2_API_KEY')
    base_url = 'https://sapi.xt.com'

    # Test public endpoint
    response = requests.get(f"{base_url}/v4/public/symbol", timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get('rc') == 0:
            symbols = data.get('result', [])
            print(f"✓ XT API is accessible ({len(symbols)} symbols available)")
        else:
            print(f"✗ XT API returned error: {data}")
    else:
        print(f"✗ XT API request failed with status {response.status_code}")
except Exception as e:
    print(f"✗ XT API test failed: {e}")

# Test 4: Test Telegram Bot API
print("\n4. Testing Telegram Bot API...")
try:
    import requests

    bot_token = env_vars.get('TELEGRAM_BOT_TOKEN')
    chat_id = env_vars.get('TELEGRAM_CHAT_ID')

    if bot_token:
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                print(f"✓ Telegram bot connected: @{bot_info.get('username')}")
            else:
                print(f"✗ Telegram API error: {data}")
        else:
            print(f"✗ Telegram API request failed with status {response.status_code}")
    else:
        print("✗ TELEGRAM_BOT_TOKEN not set")
except Exception as e:
    print(f"✗ Telegram API test failed: {e}")

# Test 5: Test DEXScreener API
print("\n5. Testing DEXScreener API...")
try:
    import requests

    url = "https://api.dexscreener.com/latest/dex/pairs/ethereum"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        pairs = data.get('pairs', [])
        print(f"✓ DEXScreener API is accessible ({len(pairs)} pairs available)")
    else:
        print(f"✗ DEXScreener API request failed with status {response.status_code}")
except Exception as e:
    print(f"✗ DEXScreener API test failed: {e}")

print("\n" + "="*60)
print("Configuration test completed!")
print("="*60)
