#!/usr/bin/env python3
"""
Test script to send a test message to Telegram
"""

import requests
import os

# Load environment variables
env_vars = {}
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()

bot_token = env_vars.get('TELEGRAM_BOT_TOKEN')
chat_id = env_vars.get('TELEGRAM_CHAT_ID')

if not bot_token or not chat_id:
    print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set!")
    exit(1)

# Send test message
url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

message = """
🤖 <b>Trinkenbot Enhanced - Test Message</b>

✅ Bot is now ready to trade!

<b>Configuration:</b>
• Spread Range: 2-3%
• Min Liquidity: $5,000
• Min Volume: $10,000
• Live Trading: ENABLED

<b>Commands:</b>
/start - Initialize bot
/status - Check bot status
/balance - View XT account balance
/stats - Trading statistics
/settings - View/change settings

Ready to catch arbitrage opportunities! 🚀
"""

payload = {
    'chat_id': chat_id,
    'text': message,
    'parse_mode': 'HTML'
}

response = requests.post(url, json=payload)
if response.status_code == 200:
    print("✓ Test message sent successfully!")
    print(f"Response: {response.json()}")
else:
    print(f"✗ Failed to send message: {response.status_code}")
    print(response.text)
