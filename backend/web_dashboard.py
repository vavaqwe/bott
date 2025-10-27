from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import json
from datetime import datetime
from pathlib import Path

app = FastAPI(title="Trinkenbot Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple dashboard HTML"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trinkenbot Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }
            .header h1 {
                font-size: 3em;
                margin-bottom: 10px;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .stat-card h3 {
                color: #667eea;
                font-size: 0.9em;
                text-transform: uppercase;
                margin-bottom: 10px;
            }
            .stat-card .value {
                font-size: 2.5em;
                font-weight: bold;
                color: #333;
            }
            .trades-section {
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .trades-section h2 {
                color: #667eea;
                margin-bottom: 20px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #667eea;
            }
            .status-badge {
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 600;
            }
            .status-running { background: #10b981; color: white; }
            .status-stopped { background: #ef4444; color: white; }
            .refresh-btn {
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1em;
                margin-top: 20px;
            }
            .refresh-btn:hover {
                background: #5568d3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Trinkenbot Enhanced</h1>
                <p>DEX Arbitrage Trading Bot</p>
                <span class="status-badge status-running" id="status">● RUNNING</span>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Signals Processed</h3>
                    <div class="value" id="signals">-</div>
                </div>
                <div class="stat-card">
                    <h3>Valid Signals</h3>
                    <div class="value" id="valid-signals">-</div>
                </div>
                <div class="stat-card">
                    <h3>Trades Executed</h3>
                    <div class="value" id="trades">-</div>
                </div>
                <div class="stat-card">
                    <h3>Success Rate</h3>
                    <div class="value" id="success-rate">-</div>
                </div>
            </div>
            
            <div class="trades-section">
                <h2>Recent Trades</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Token</th>
                            <th>Side</th>
                            <th>Spread</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="trades-table">
                        <tr>
                            <td colspan="5" style="text-align: center; color: #999;">No trades yet</td>
                        </tr>
                    </tbody>
                </table>
                <button class="refresh-btn" onclick="loadData()">Refresh Data</button>
            </div>
        </div>
        
        <script>
            async function loadData() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    
                    document.getElementById('signals').textContent = data.signals_processed || 0;
                    document.getElementById('valid-signals').textContent = data.valid_signals || 0;
                    document.getElementById('trades').textContent = data.trades_executed || 0;
                    
                    const rate = data.signals_processed > 0 
                        ? ((data.valid_signals / data.signals_processed) * 100).toFixed(1) + '%'
                        : '0%';
                    document.getElementById('success-rate').textContent = rate;
                    
                    // Load trades
                    const tradesResponse = await fetch('/api/trades');
                    const trades = await tradesResponse.json();
                    
                    const tbody = document.getElementById('trades-table');
                    if (trades.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #999;">No trades yet</td></tr>';
                    } else {
                        tbody.innerHTML = trades.slice(-10).reverse().map(trade => `
                            <tr>
                                <td>${new Date(trade.timestamp).toLocaleString()}</td>
                                <td>${trade.symbol}</td>
                                <td>${trade.side}</td>
                                <td>${trade.signal_data?.spread?.toFixed(2) || 'N/A'}%</td>
                                <td><span class="status-badge status-running">✓ Executed</span></td>
                            </tr>
                        `).join('');
                    }
                } catch (error) {
                    console.error('Error loading data:', error);
                    document.getElementById('status').textContent = '● ERROR';
                    document.getElementById('status').className = 'status-badge status-stopped';
                }
            }
            
            // Load data on page load
            loadData();
            
            // Auto-refresh every 10 seconds
            setInterval(loadData, 10000);
        </script>
    </body>
    </html>
    """
    return html

@app.get("/api/stats")
async def get_stats() -> Dict:
    """Get bot statistics"""
    try:
        stats_file = Path('bot_stats.json')
        if stats_file.exists():
            with open(stats_file, 'r') as f:
                return json.load(f)
        return {
            'signals_processed': 0,
            'valid_signals': 0,
            'trades_executed': 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades")
async def get_trades() -> List[Dict]:
    """Get recent trades"""
    try:
        trades_file = Path('trades.json')
        if trades_file.exists():
            with open(trades_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)