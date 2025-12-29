# Kalshi Arbitrage Scanner API Documentation

## Base URL
- Development: `http://localhost:8000/api`
- Production: Configured via environment

## Authentication
The API uses Kalshi API credentials configured in the `.env` file. No additional authentication is required for the scanner API itself.

## Endpoints

### Configuration

#### GET /config
Get current configuration status.

**Response:**
```json
{
  "environment": "demo",
  "kalshiConnected": true,
  "spotPricesEnabled": true
}
```

#### POST /config/environment
Switch between demo and production environments.

**Request:**
```json
{
  "environment": "demo"
}
```

---

### Markets

#### GET /markets
Get all grouped markets.

**Query Parameters:**
- `asset` (optional): Filter by asset (BTC, ETH, etc.)

**Response:**
```json
{
  "groups": [
    {
      "asset": "BTC",
      "settlementTime": "2025-01-15T20:00:00Z",
      "spotPrice": 96500.50,
      "isComplete": true,
      "thresholds": [...],
      "brackets": [...]
    }
  ]
}
```

---

### Opportunities

#### GET /opportunities
Get current arbitrage opportunities.

**Query Parameters:**
- `min_profit` (default: 1.0): Minimum profit percentage
- `asset` (optional): Filter by asset

**Response:**
```json
{
  "opportunities": [
    {
      "id": "uuid",
      "asset": "BTC",
      "thresholdStrike": 95000,
      "thresholdYesPrice": 0.70,
      "impliedPrice": 0.60,
      "divergence": 0.10,
      "netProfitPct": 5.5,
      "maxLiquidityUsd": 500,
      "score": 75.5,
      "tradeDirection": "buy_brackets"
    }
  ]
}
```

---

### Spot Prices

#### GET /spot-prices
Get current spot prices from CF Benchmarks.

**Response:**
```json
{
  "prices": {
    "BTC": {
      "price": 96500.50,
      "timestamp": "2025-01-10T12:00:00Z",
      "cached": false
    },
    "ETH": {
      "price": 3250.25,
      "timestamp": "2025-01-10T12:00:00Z",
      "cached": false
    }
  }
}
```

---

### Account

#### GET /balance
Get account balance.

**Response:**
```json
{
  "availableBalance": 1500.00,
  "totalBalance": 2000.00
}
```

#### GET /positions
Get open positions.

---

### Trading

#### POST /trade
Execute an arbitrage trade.

**Request:**
```json
{
  "opportunity_id": "uuid",
  "position_size": 100.00
}
```

**Response:**
```json
{
  "result": {
    "tradeId": "uuid",
    "status": "success",
    "totalCost": 95.00,
    "totalFees": 2.50,
    "expectedPayout": 100.00,
    "expectedProfit": 2.50,
    "orders": [...]
  },
  "sizingSuggestions": {
    "conservative": 30.00,
    "moderate": 75.00,
    "aggressive": 150.00
  }
}
```

#### GET /trade/suggestions/{opportunity_id}
Get trade sizing suggestions.

---

### History

#### GET /history/opportunities
Get historical opportunities.

**Query Parameters:**
- `asset` (optional)
- `start_date` (optional): ISO date
- `end_date` (optional): ISO date
- `min_profit` (optional)
- `traded_only` (optional): Boolean
- `limit` (default: 100)

#### GET /history/trades
Get trade history.

---

### Analytics

#### GET /analytics/summary
Get analytics summary.

**Query Parameters:**
- `period`: today, week, month, all
- `asset` (optional)

#### GET /analytics/by-asset
Get breakdown by asset.

#### GET /analytics/by-date
Get breakdown by date.

#### GET /analytics/export
Export data as CSV.

---

## WebSocket

Connect to `/ws` for real-time updates.

### Message Types

**Spot Prices:**
```json
{
  "type": "spot_prices",
  "data": {
    "BTC": { "price": 96500.50, "timestamp": "...", "cached": false }
  }
}
```

**Opportunities:**
```json
{
  "type": "opportunities",
  "data": [
    { "id": "...", "asset": "BTC", "netProfitPct": 5.5, ... }
  ]
}
```

**Ping/Pong:**
```json
{ "type": "ping" }
{ "type": "pong" }
```
