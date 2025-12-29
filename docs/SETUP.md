# Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Kalshi API credentials (demo or production)

## Getting Kalshi API Credentials

1. Go to [Kalshi](https://kalshi.com) and create an account
2. Navigate to Settings > API Keys
3. Generate a new API key pair
4. Download the private key (PEM file)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd kalshi-arb-scanner
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
KALSHI_ENV=demo
KALSHI_API_KEY_ID=your-key-id-here
KALSHI_PRIVATE_KEY_PATH=./keys/kalshi-private-key.pem
```

### 3. Install Private Key

Place your Kalshi private key in the keys directory:

```bash
cp /path/to/your/kalshi-private-key.pem ./keys/
chmod 600 ./keys/kalshi-private-key.pem
```

### 4. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Frontend Setup

```bash
cd frontend
npm install
```

## Running the Application

### Development Mode

**Backend (Terminal 1):**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Frontend (Terminal 2):**
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

### Production Mode (Docker)

```bash
docker-compose up --build
```

Open http://localhost in your browser.

## Testing

### Run Backend Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

### Run Frontend Type Checks

```bash
cd frontend
npm run lint
```

## Troubleshooting

### Common Issues

**"Authentication failed"**
- Verify your API key ID is correct in `.env`
- Ensure the private key path is correct
- Check that the private key file permissions are correct

**"No opportunities found"**
- This is normal when markets are properly priced
- Try adjusting `min_profit` parameter to a lower value

**WebSocket disconnects**
- Check backend logs for errors
- Verify CORS settings if running on different ports

**Database errors**
- Ensure the `data/` directory exists and is writable
- Delete `data/kalshi_arb.db` to reset the database

## Switching to Production

1. Update `.env`:
   ```env
   KALSHI_ENV=production
   ```

2. Use production API credentials
3. Review risk settings in the application
4. Start with small position sizes to verify everything works

**Warning:** Production mode uses real money. Always test thoroughly in demo mode first.
