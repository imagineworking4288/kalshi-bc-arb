const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers }
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }
  return response.json();
}

export const api = {
  getConfig: () => fetchJson<{ paper_mode: boolean; api_configured: boolean }>('/config'),

  getSpotPrice: () => fetchJson<{ asset: string; price: number; timestamp: string; source: string }>('/spot-price'),

  getOpportunities: (minProfit = 1.0) =>
    fetchJson<{ opportunities: any[]; count: number; paper_mode: boolean }>(
      `/opportunities?min_profit=${minProfit}`
    ),

  getBalance: () => fetchJson<any>('/balance'),

  getPositions: () => fetchJson<{ positions: any[]; paper_mode: boolean }>('/positions'),

  executeArbitrage: (opportunityId: string, numContracts: number) =>
    fetchJson<any>('/execute', {
      method: 'POST',
      body: JSON.stringify({ opportunity_id: opportunityId, num_contracts: numContracts })
    }),

  resetPaper: (startingBalance?: number) =>
    fetchJson<any>('/paper/reset', {
      method: 'POST',
      body: JSON.stringify({ starting_balance: startingBalance })
    }),

  getPaperSummary: () => fetchJson<any>('/paper/summary'),

  getPaperTrades: (limit = 50) => fetchJson<{ trades: any[] }>(`/paper/trades?limit=${limit}`),

  // Manual Trading
  placeTrade: (params: {
    ticker: string;
    side: 'yes' | 'no';
    action: 'buy' | 'sell';
    count: number;
    price_cents: number;
    modes: ('paper' | 'live')[];
  }) =>
    fetchJson<{
      results: Array<{
        mode: string;
        order_id: string;
        status: string;
        error?: string;
      }>;
      success: boolean;
      message: string;
    }>('/trade/place', {
      method: 'POST',
      body: JSON.stringify(params)
    }),

  getMarketDetails: (ticker: string) =>
    fetchJson<{
      ticker: string;
      title: string;
      subtitle: string;
      status: string;
      yes_ask: number;
      no_ask: number;
      yes_bid: number;
      no_bid: number;
      volume: number;
      open_interest: number;
      close_time: string;
      expiration_time: string;
    }>(`/trade/market/${ticker}`),

  // Portfolio
  getPortfolioSummary: () =>
    fetchJson<{
      paper_balance: number;
      live_balance: number;
      paper_positions_count: number;
      live_positions_count: number;
    }>('/portfolio/summary'),

  getPortfolioPositions: () =>
    fetchJson<{
      positions: Array<{
        ticker: string;
        side: string;
        contracts: number;
        avg_price: number;
        total_cost: number;
        mode: string;
        created_at: string;
      }>;
    }>('/portfolio/positions'),

  getPortfolioOrders: (mode?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (mode) params.append('mode', mode);
    params.append('limit', limit.toString());
    return fetchJson<{
      orders: Array<{
        id: string;
        ticker: string;
        side: string;
        action: string;
        count: number;
        price_cents: number;
        mode: string;
        status: string;
        created_at: string;
      }>;
    }>(`/portfolio/orders?${params}`);
  },

  // Watchlist
  getWatchlist: () =>
    fetchJson<{
      items: Array<{
        id: string;
        ticker: string;
        title: string;
        subtitle: string;
        notes: string | null;
        added_at: string;
        yes_ask: number | null;
        no_ask: number | null;
        status: string;
      }>;
    }>('/watchlist'),

  addToWatchlist: (ticker: string, notes?: string) =>
    fetchJson<{
      id: string;
      ticker: string;
      title: string;
      subtitle: string;
      notes: string | null;
      already_existed: boolean;
    }>('/watchlist', {
      method: 'POST',
      body: JSON.stringify({ ticker, notes })
    }),

  removeFromWatchlist: (ticker: string) =>
    fetchJson<{ message: string }>(`/watchlist/${ticker}`, {
      method: 'DELETE'
    }),

  // Weather Arbitrage
  getWeatherStatus: () => fetchJson<any>('/weather-arb/status'),

  // Predictions API
  getSupportedCities: () =>
    fetchJson<{
      cities: Array<{
        code: string;
        latitude: number;
        longitude: number;
        timezone: string;
      }>;
    }>('/predictions/cities'),

  getPredictions: (city: string, forceRefresh = false) =>
    fetchJson<{
      city: string;
      event_ticker: string;
      forecast: {
        city: string;
        forecast_high: number;
        forecast_low: number;
        weather_pattern: string;
        short_forecast: string;
        source: string;
        fetched_at: string;
        cached: boolean;
        cache_age_seconds: number;
      };
      brackets: Array<{
        ticker: string;
        label: string;
        model_probability: number;
        market_implied_probability: number;
        probability_edge: number;
        yes_price_cents: number | null;
        no_price_cents: number | null;
        yes_ev_after_fee: number;
        no_ev_after_fee: number;
        recommended_action: string;
        recommended_side: string | null;
        recommended_contracts: number;
        kelly_fraction: number;
        has_existing_position: boolean;
        position_conflict: boolean;
        confidence: number;
      }>;
      total_probability: number;
      has_opportunities: boolean;
      best_opportunity: any | null;
      warnings: string[];
      generated_at: string;
    }>(`/predictions/${city}?force_refresh=${forceRefresh}`),

  getForecast: (city: string, forceRefresh = false) =>
    fetchJson<{
      city: string;
      forecast_high: number;
      forecast_low: number;
      weather_pattern: string;
      short_forecast: string;
      source: string;
      fetched_at: string;
      cached: boolean;
      cache_age_seconds: number;
    }>(`/predictions/${city}/forecast?force_refresh=${forceRefresh}`),

  refreshForecast: (city: string) =>
    fetchJson<{
      success: boolean;
      city: string;
      source: string;
      forecast_high: number;
      forecast_low: number;
    }>(`/predictions/${city}/refresh`, { method: 'POST' }),

  getPredictionStatus: () =>
    fetchJson<{
      circuits: { nws: string; open_meteo: string };
      supported_cities: string[];
      cache_entries: number;
    }>('/predictions/status'),

  resetPredictionCircuits: () =>
    fetchJson<{
      success: boolean;
      circuits: { nws: string; open_meteo: string };
    }>('/predictions/reset-circuits', { method: 'POST' }),
};
