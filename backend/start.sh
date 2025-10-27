#!/bin/bash
# Trinkenbot Enhanced - Quick Start Script

echo "=================================================="
echo "  Trinkenbot Enhanced - Starting..."
echo "=================================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with your API keys"
    exit 1
fi

echo "✓ .env file found"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
echo "✓ Python version: $PYTHON_VERSION"

# Check if required modules are installed
echo "Checking dependencies..."
python3 -c "import dotenv, requests, aiohttp, web3" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠ Installing missing dependencies..."
    python3 -m pip install --quiet --break-system-packages python-dotenv requests aiohttp web3
    if [ $? -eq 0 ]; then
        echo "✓ Dependencies installed"
    else
        echo "❌ Failed to install dependencies"
        exit 1
    fi
else
    echo "✓ All dependencies installed"
fi

# Check API connectivity
echo ""
echo "Testing API connections..."
python3 test_bot.py 2>&1 | grep -E "✓|✗"
echo ""

# Create necessary JSON files
[ ! -f positions.json ] && echo '{}' > positions.json
[ ! -f trades.json ] && echo '[]' > trades.json
[ ! -f bot_stats.json ] && echo '{}' > bot_stats.json
echo "✓ State files initialized"

echo ""
echo "=================================================="
echo "  Starting Trinkenbot Enhanced..."
echo "=================================================="
echo ""
echo "Bot will start monitoring DEX markets"
echo "Telegram commands available: /start /status /balance /stats"
echo ""
echo "Press Ctrl+C to stop the bot"
echo ""
echo "=================================================="
echo ""

# Start the bot
python3 main.py
