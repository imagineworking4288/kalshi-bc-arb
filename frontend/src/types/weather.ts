// Weather scanner status from GET /weather-arb/status
export interface WeatherStatus {
  running: boolean;
  scan_count: number;
  last_scan: string | null;
  cities: Record<string, CityResult>;
  opportunities: WeatherOpportunity[];
  near_misses: NearMissRecord[];
  forecasts: Record<string, ForecastData>;
  stats: {
    total_cities: number;
    total_series: number;
    total_arbitrage: number;
    total_near_miss: number;
    best_cost: number | null;
  };
}

export interface CityResult {
  code: string;
  city: string;
  high: SeriesResult | null;
  low: SeriesResult | null;
}

export interface SeriesResult {
  series: string;
  market_type: 'high' | 'low';
  bracket_count: number;
  brackets: BracketMarket[];
  best_cost: number | null;
  totals: BracketTotals | null;
  arbitrage: ArbitrageAnalysis | null;
  opportunities: WeatherOpportunity[];
  near_misses: NearMissRecord[];
  forecast: SeriesForecast | null;
  error: string | null;
}

export interface BracketTotals {
  yes_ask: number;
  yes_bid: number;
  no_ask: number;
  no_bid: number;
  volume: number;
}

export interface ArbitrageStrategy {
  cost: number;
  fees: number;
  net_cost: number;
  payout: number;
  gross_profit: number;
  net_profit: number;
  is_arb: boolean;
  brackets_used?: number;
  brackets?: { title: string; no_ask: number }[];
}

export interface ArbitrageAnalysis {
  all_yes: ArbitrageStrategy;
  all_no: ArbitrageStrategy;
  min_2_no: ArbitrageStrategy;
  best_strategy: string | null;
  has_arbitrage: boolean;
}

export interface BracketMarket {
  ticker: string;
  title: string;
  floor_strike: number | null;
  cap_strike: number | null;
  yes_ask: number;
  yes_bid: number;
  no_ask: number;
  no_bid: number;
  volume: number;
}

export interface SeriesForecast {
  raw_temp: number;
  adjusted_temp: number;
  uncertainty: number;
  description: string;
}

export interface ForecastData {
  high: number | null;
  low: number | null;
  high_description: string;
  low_description: string;
  high_detailed: string;
  low_detailed: string;
  fetched_at: string;
  location_code: string;
  forecast_date: string;
}

export interface WeatherOpportunity {
  city_code: string;
  city_name: string;
  market_type: 'high' | 'low';
  series_ticker: string;
  event_ticker: string;
  total_cost: number;
  gross_profit: number;
  net_profit: number;
  bracket_count: number;
  brackets: BracketMarket[];
  forecast_temp: number | null;
  forecast_uncertainty: number;
  found_at: string;
}

export interface NearMissRecord {
  city_code: string;
  city_name: string;
  market_type: 'high' | 'low';
  series_ticker: string;
  event_ticker: string;
  total_cost: number;
  distance: number;
  bracket_count: number;
}

export type CostStatus = 'opportunity' | 'near_miss' | 'neutral' | 'negative';

export function getCostStatus(cost: number | null): CostStatus {
  if (cost === null) return 'neutral';
  if (cost < 100) return 'opportunity';
  if (cost <= 102) return 'near_miss';
  if (cost <= 105) return 'neutral';
  return 'negative';
}

export function getCostColor(status: CostStatus): string {
  switch (status) {
    case 'opportunity': return 'text-green-400';
    case 'near_miss': return 'text-yellow-400';
    case 'neutral': return 'text-gray-400';
    case 'negative': return 'text-red-400';
  }
}

export function getCostBgColor(status: CostStatus): string {
  switch (status) {
    case 'opportunity': return 'bg-green-500/20 border-green-500';
    case 'near_miss': return 'bg-yellow-500/20 border-yellow-500';
    case 'neutral': return 'bg-gray-700 border-gray-600';
    case 'negative': return 'bg-red-500/20 border-red-500';
  }
}
