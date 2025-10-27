#!/bin/bash

# Start Trinkenbot Enhanced

echo "Starting Trinkenbot Enhanced..."
echo "================================"

cd /app/backend

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found!"
    echo "Please create .env file with required configuration"
    exit 1
fi

# Run the bot
python3 main.py