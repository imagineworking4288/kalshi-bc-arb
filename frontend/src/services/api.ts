import type {
  Config,
  MarketGroup,
  Opportunity,
  SpotPrices,
  TradeResult,
  SizingSuggestions,
  AnalyticsSummary,
  AssetBreakdown,
  DateBreakdown,
  HourBreakdown,
  ProfitDistribution,
  TradePerformance,
  PnLSummary,
  Balance,
  HistoricalOpportunity,
  HistoricalTrade,
  TradeDetails,
} from '../types';

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `API error: ${response.status}`);
  }

  return response.json();
}

// Transform API response keys from snake_case to camelCase
function transformKeys(obj: Record<string, unknown>): Record<string, unknown> {
  if (Array.isArray(obj)) {
    return obj.map(item =>
      typeof item === 'object' && item !== null
        ? transformKeys(item as Record<string, unknown>)
        : item
    ) as unknown as Record<string, unknown>;
  }

  if (typeof obj !== 'object' || obj === null) {
    return obj;
  }

  const transformed: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    transformed[camelKey] = typeof value === 'object' && value !== null
      ? transformKeys(value as Record<string, unknown>)
      : value;
  }
  return transformed;
}

export const api = {
  // Config
  getConfig: async (): Promise<Config> => {
    const data = await fetchJson<Record<string, unknown>>('/config');
    return transformKeys(data) as unknown as Config;
  },

  switchEnvironment: (environment: 'demo' | 'production') =>
    fetchJson<{ status: string }>('/config/environment', {
      method: 'POST',
      body: JSON.stringify({ environment }),
    }),

  // Markets
  getMarkets: async (asset?: string): Promise<{ groups: MarketGroup[] }> => {
    const params = asset ? `?asset=${asset}` : '';
    const data = await fetchJson<Record<string, unknown>>(`/markets${params}`);
    return transformKeys(data) as unknown as { groups: MarketGroup[] };
  },

  // Opportunities
  getOpportunities: async (
    minProfit = 1.0,
    asset?: string
  ): Promise<{ opportunities: Opportunity[] }> => {
    const params = new URLSearchParams({ min_profit: minProfit.toString() });
    if (asset) params.append('asset', asset);
    const data = await fetchJson<Record<string, unknown>>(`/opportunities?${params}`);
    return transformKeys(data) as unknown as { opportunities: Opportunity[] };
  },

  getOpportunity: async (id: string): Promise<HistoricalOpportunity> => {
    const data = await fetchJson<Record<string, unknown>>(`/opportunities/${id}`);
    return transformKeys(data) as unknown as HistoricalOpportunity;
  },

  // Spot prices
  getSpotPrices: async (): Promise<{ prices: SpotPrices }> => {
    const data = await fetchJson<Record<string, unknown>>('/spot-prices');
    return transformKeys(data) as unknown as { prices: SpotPrices };
  },

  // Balance
  getBalance: async (): Promise<Balance> => {
    const data = await fetchJson<Record<string, unknown>>('/balance');
    return transformKeys(data) as unknown as Balance;
  },

  // Trading
  executeTrade: async (
    opportunityId: string,
    positionSize: number
  ): Promise<{ result: TradeResult; sizingSuggestions: SizingSuggestions }> => {
    const data = await fetchJson<Record<string, unknown>>('/trade', {
      method: 'POST',
      body: JSON.stringify({
        opportunity_id: opportunityId,
        position_size: positionSize,
      }),
    });
    return transformKeys(data) as unknown as { result: TradeResult; sizingSuggestions: SizingSuggestions };
  },

  getTradeSuggestions: async (
    opportunityId: string,
    positionSize?: number
  ): Promise<{ suggestions: SizingSuggestions; balance: number; tradeDetails: TradeDetails | null }> => {
    const params = positionSize ? `?position_size=${positionSize}` : '';
    const data = await fetchJson<Record<string, unknown>>(`/trade/suggestions/${opportunityId}${params}`);
    return transformKeys(data) as unknown as { suggestions: SizingSuggestions; balance: number; tradeDetails: TradeDetails | null };
  },

  // Positions
  getPositions: async (): Promise<{ positions: unknown[] }> => {
    const data = await fetchJson<Record<string, unknown>>('/positions');
    return transformKeys(data) as unknown as { positions: unknown[] };
  },

  // History
  getOpportunityHistory: async (params?: {
    asset?: string;
    startDate?: string;
    endDate?: string;
    minProfit?: number;
    tradedOnly?: boolean;
    limit?: number;
  }): Promise<{ opportunities: HistoricalOpportunity[] }> => {
    const searchParams = new URLSearchParams();
    if (params?.asset) searchParams.append('asset', params.asset);
    if (params?.startDate) searchParams.append('start_date', params.startDate);
    if (params?.endDate) searchParams.append('end_date', params.endDate);
    if (params?.minProfit) searchParams.append('min_profit', params.minProfit.toString());
    if (params?.tradedOnly) searchParams.append('traded_only', 'true');
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    const data = await fetchJson<Record<string, unknown>>(`/history/opportunities?${searchParams}`);
    return transformKeys(data) as unknown as { opportunities: HistoricalOpportunity[] };
  },

  getTradeHistory: async (params?: {
    asset?: string;
    limit?: number;
  }): Promise<{ trades: HistoricalTrade[] }> => {
    const searchParams = new URLSearchParams();
    if (params?.asset) searchParams.append('asset', params.asset);
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    const data = await fetchJson<Record<string, unknown>>(`/history/trades?${searchParams}`);
    return transformKeys(data) as unknown as { trades: HistoricalTrade[] };
  },

  // Analytics
  getAnalyticsSummary: async (
    period = 'week',
    asset?: string
  ): Promise<AnalyticsSummary> => {
    const params = new URLSearchParams({ period });
    if (asset) params.append('asset', asset);
    const data = await fetchJson<Record<string, unknown>>(`/analytics/summary?${params}`);
    return transformKeys(data) as unknown as AnalyticsSummary;
  },

  getAnalyticsByAsset: async (
    startDate?: string,
    endDate?: string
  ): Promise<{ byAsset: AssetBreakdown[] }> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const data = await fetchJson<Record<string, unknown>>(`/analytics/by-asset?${params}`);
    return transformKeys(data) as unknown as { byAsset: AssetBreakdown[] };
  },

  getAnalyticsByDate: async (
    startDate?: string,
    endDate?: string,
    asset?: string
  ): Promise<{ byDate: DateBreakdown[] }> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (asset) params.append('asset', asset);
    const data = await fetchJson<Record<string, unknown>>(`/analytics/by-date?${params}`);
    return transformKeys(data) as unknown as { byDate: DateBreakdown[] };
  },

  getAnalyticsByHour: async (
    startDate?: string,
    endDate?: string,
    asset?: string
  ): Promise<{ byHour: HourBreakdown[] }> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (asset) params.append('asset', asset);
    const data = await fetchJson<Record<string, unknown>>(`/analytics/by-hour?${params}`);
    return transformKeys(data) as unknown as { byHour: HourBreakdown[] };
  },

  getProfitDistribution: async (
    startDate?: string,
    endDate?: string,
    asset?: string,
    binSize = 0.5
  ): Promise<{ distribution: ProfitDistribution[] }> => {
    const params = new URLSearchParams({ bin_size: binSize.toString() });
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (asset) params.append('asset', asset);
    const data = await fetchJson<Record<string, unknown>>(`/analytics/profit-distribution?${params}`);
    return transformKeys(data) as unknown as { distribution: ProfitDistribution[] };
  },

  getTradePerformance: async (
    startDate?: string,
    endDate?: string
  ): Promise<TradePerformance> => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const data = await fetchJson<Record<string, unknown>>(`/analytics/trade-performance?${params}`);
    return transformKeys(data) as unknown as TradePerformance;
  },

  getPnLSummary: async (): Promise<PnLSummary> => {
    const data = await fetchJson<Record<string, unknown>>('/analytics/pnl');
    return transformKeys(data) as unknown as PnLSummary;
  },

  getExportUrl: (
    startDate?: string,
    endDate?: string,
    asset?: string
  ): string => {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (asset) params.append('asset', asset);
    return `${API_BASE}/analytics/export?${params}`;
  },
};
