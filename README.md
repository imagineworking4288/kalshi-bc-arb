# Kalshi Arbitrage Scanner

Detects and executes arbitrage opportunities between Kalshi threshold and bracket markets.

## Quick Start

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env
# Edit .env with your settings
python -m uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Trading Modes

- **Paper Mode** (default): Uses real market data, simulates trades locally
- **Live Mode**: Executes real trades on Kalshi (real money!)

## Safety

Paper mode is enabled by default. To switch to live:
1. Set `PAPER_TRADING_MODE=false` in `.env`
2. Add your Kalshi API credentials
3. Restart the backend
4. Type "LIVE" in the UI to confirm
