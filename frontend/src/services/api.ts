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
};
