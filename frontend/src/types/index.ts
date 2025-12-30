export type TradingMode = 'paper' | 'live';

export interface Bracket {
  ticker: string;
  low: number;
  high: number;
  yes_price: number;
}

export interface Opportunity {
  id: string;
  asset: string;
  settlement_time: string;
  threshold_ticker: string;
  threshold_title: string;
  threshold_strike: number;
  bracket_count: number;
  cost_per_set: number;
  fees_per_set: number;
  profit_per_set: number;
  net_profit_pct: number;
  max_contracts: number;
  max_liquidity_usd: number;
  spot_price: number | null;
  brackets: Bracket[];
}

export interface Balance {
  available_balance: number;
  starting_balance?: number;
  paper_mode: boolean;
}

export interface Position {
  id: string;
  ticker: string;
  side: string;
  contracts: number;
  avg_price: number;
  total_cost: number;
  total_fees: number;
  settlement_time: string;
  settled: number;
  realized_pnl?: number;
}

export interface Trade {
  id: string;
  executed_at: string;
  asset: string;
  total_cost: number;
  total_fees: number;
  expected_payout: number;
  expected_profit: number;
  expected_profit_pct: number;
  status: string;
}

export interface PnLSummary {
  current_balance: number;
  starting_balance: number;
  total_pnl: number;
  total_pnl_pct: number;
  realized_pnl: number;
  open_positions_value: number;
  total_trades: number;
}

export interface TradeResult {
  trade_id: string;
  status: string;
  total_cost: number;
  total_fees: number;
  expected_payout: number;
  expected_profit: number;
  message: string;
  paper_mode: boolean;
  orders: Array<{
    ticker: string;
    contracts: number;
    price: number;
    fee: number;
  }>;
}
