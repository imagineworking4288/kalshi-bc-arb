-- Opportunities table: stores all detected arbitrage opportunities
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    detected_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,

    -- Market identification
    asset TEXT NOT NULL,
    settlement_time TIMESTAMP NOT NULL,
    threshold_ticker TEXT NOT NULL,
    threshold_strike REAL NOT NULL,
    threshold_direction TEXT NOT NULL,

    -- Prices at detection
    threshold_yes_price REAL NOT NULL,
    implied_price REAL NOT NULL,
    divergence REAL NOT NULL,
    spot_price REAL,

    -- Calculated fields
    gross_profit_pct REAL NOT NULL,
    estimated_fees REAL NOT NULL,
    net_profit_pct REAL NOT NULL,
    max_liquidity_usd REAL NOT NULL,

    -- Trade direction
    trade_direction TEXT,

    -- Outcome tracking
    was_traded INTEGER DEFAULT 0,
    trade_id TEXT,

    -- Duration
    duration_seconds INTEGER,

    -- Raw data snapshot
    brackets_snapshot TEXT  -- JSON
);

CREATE INDEX IF NOT EXISTS idx_opportunities_asset ON opportunities(asset);
CREATE INDEX IF NOT EXISTS idx_opportunities_detected ON opportunities(detected_at);
CREATE INDEX IF NOT EXISTS idx_opportunities_profit ON opportunities(net_profit_pct);
CREATE INDEX IF NOT EXISTS idx_opportunities_settlement ON opportunities(settlement_time);

-- Trades table: stores executed trades
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    executed_at TIMESTAMP NOT NULL,

    -- Trade details
    asset TEXT NOT NULL,
    total_cost REAL NOT NULL,
    total_fees REAL NOT NULL,
    expected_payout REAL NOT NULL,
    expected_profit REAL NOT NULL,

    -- Execution results
    status TEXT NOT NULL,  -- 'pending', 'filled', 'partial', 'failed'
    actual_cost REAL,
    actual_fees REAL,

    -- Settlement
    settled_at TIMESTAMP,
    actual_payout REAL,
    actual_profit REAL,

    -- Order details
    orders_json TEXT,  -- JSON array of order details

    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_opportunity ON trades(opportunity_id);

-- Positions table: tracks open positions
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    contracts INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    close_price REAL,
    pnl REAL,

    FOREIGN KEY (trade_id) REFERENCES trades(id)
);

CREATE INDEX IF NOT EXISTS idx_positions_trade ON positions(trade_id);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);

-- Settings table: stores user settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Price history table: stores historical spot prices
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    price REAL NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_history_asset ON price_history(asset);
CREATE INDEX IF NOT EXISTS idx_price_history_timestamp ON price_history(timestamp);
