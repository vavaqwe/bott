#!/bin/bash

# Run bot with dashboard

echo "Starting Trinkenbot Enhanced with Dashboard..."
echo "="*50

cd /app/backend

# Start dashboard in background
echo "Starting dashboard on port 8001..."
python3 web_dashboard.py > dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "Dashboard PID: $DASHBOARD_PID"

sleep 2

# Start bot
echo "Starting trading bot..."
python3 main.py

# Cleanup on exit
kill $DASHBOARD_PID 2>/dev/null