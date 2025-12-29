import { create } from 'zustand';
import type {
  AnalyticsSummary,
  AssetBreakdown,
  DateBreakdown,
  HourBreakdown,
  ProfitDistribution,
  TradePerformance,
  PnLSummary,
} from '../types';

interface AnalyticsState {
  period: 'today' | 'week' | 'month' | 'all';
  selectedAsset: string | null;
  summary: AnalyticsSummary | null;
  byAsset: AssetBreakdown[];
  byDate: DateBreakdown[];
  byHour: HourBreakdown[];
  profitDistribution: ProfitDistribution[];
  tradePerformance: TradePerformance | null;
  pnlSummary: PnLSummary | null;
  isLoading: boolean;
  error: string | null;

  setPeriod: (period: 'today' | 'week' | 'month' | 'all') => void;
  setSelectedAsset: (asset: string | null) => void;
  setSummary: (summary: AnalyticsSummary) => void;
  setByAsset: (data: AssetBreakdown[]) => void;
  setByDate: (data: DateBreakdown[]) => void;
  setByHour: (data: HourBreakdown[]) => void;
  setProfitDistribution: (data: ProfitDistribution[]) => void;
  setTradePerformance: (data: TradePerformance) => void;
  setPnLSummary: (data: PnLSummary) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAnalyticsStore = create<AnalyticsState>((set) => ({
  period: 'week',
  selectedAsset: null,
  summary: null,
  byAsset: [],
  byDate: [],
  byHour: [],
  profitDistribution: [],
  tradePerformance: null,
  pnlSummary: null,
  isLoading: false,
  error: null,

  setPeriod: (period) => set({ period }),
  setSelectedAsset: (selectedAsset) => set({ selectedAsset }),
  setSummary: (summary) => set({ summary }),
  setByAsset: (byAsset) => set({ byAsset }),
  setByDate: (byDate) => set({ byDate }),
  setByHour: (byHour) => set({ byHour }),
  setProfitDistribution: (profitDistribution) => set({ profitDistribution }),
  setTradePerformance: (tradePerformance) => set({ tradePerformance }),
  setPnLSummary: (pnlSummary) => set({ pnlSummary }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}));
