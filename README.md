# Kalshi Arbitrage Scanner

A web application that detects and enables execution of arbitrage opportunities between Kalshi's threshold markets ("Will BTC be above $X?") and bracket markets ("BTC price range $X-$Y").

## Core Concept

When Kalshi offers both threshold and bracket markets for the same asset and settlement time, mathematical constraints require that the threshold price equals the sum of all bracket prices above that threshold. When prices diverge, guaranteed profit exists.

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 18 with TypeScript, Vite, Tailwind CSS, Zustand
- **Database**: SQLite
- **External APIs**: Kalshi REST/WebSocket, CF Benchmarks (crypto spot prices)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Kalshi API credentials (demo or production)

### Setup

1. Clone the repository:
```bash
git clone <repo-url>
cd kalshi-arb-scanner
```

2. Copy environment file and configure:
```bash
cp .env.example .env
# Edit .env with your Kalshi API credentials
```

3. Place your Kalshi private key:
```bash
cp /path/to/your/kalshi-private-key.pem ./keys/
```

4. Install backend dependencies:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

5. Install frontend dependencies:
```bash
cd frontend
npm install
```

### Running the Application

1. Start the backend:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

2. Start the frontend (in a new terminal):
```bash
cd frontend
npm run dev
```

3. Open http://localhost:5173 in your browser

### Docker

Alternatively, use Docker:
```bash
docker-compose up --build
```

## Features

- **Real-time Market Monitoring**: Fetches and classifies Kalshi markets automatically
- **Divergence Detection**: Identifies arbitrage opportunities with configurable profit thresholds
- **Spot Price Integration**: Shows current BTC/ETH prices from CF Benchmarks
- **Trade Execution**: Execute multi-leg arbitrage trades with position sizing suggestions
- **Position Tracking**: Monitor open positions and P&L
- **Analytics Dashboard**: Historical opportunity analysis and statistics
- **Configurable Alerts**: Visual, audio, and browser notifications

## API Documentation

See [docs/API.md](docs/API.md) for full API documentation.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system architecture details.

## Safety Notes

- **Always start with demo mode** to test the system
- **Verify all trades manually** before enabling automatic execution
- **Set appropriate risk limits** in the settings
- **Monitor positions actively** especially near settlement time

## License

MIT
