import { create } from 'zustand';
import type { Opportunity, SpotPrices, Balance } from '../types';

interface OpportunityState {
  opportunities: Opportunity[];
  spotPrices: SpotPrices;
  balance: Balance | null;
  selectedOpportunityId: string | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  connectionStatus: 'connected' | 'disconnected' | 'error' | 'failed';

  setOpportunities: (opportunities: Opportunity[]) => void;
  setSpotPrices: (prices: SpotPrices) => void;
  setBalance: (balance: Balance) => void;
  selectOpportunity: (id: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setConnectionStatus: (status: 'connected' | 'disconnected' | 'error' | 'failed') => void;
  getSelectedOpportunity: () => Opportunity | null;
}

export const useOpportunityStore = create<OpportunityState>((set, get) => ({
  opportunities: [],
  spotPrices: {},
  balance: null,
  selectedOpportunityId: null,
  isLoading: false,
  error: null,
  lastUpdated: null,
  connectionStatus: 'disconnected',

  setOpportunities: (opportunities) =>
    set({ opportunities, lastUpdated: new Date(), error: null }),

  setSpotPrices: (spotPrices) => set({ spotPrices }),

  setBalance: (balance) => set({ balance }),

  selectOpportunity: (id) => set({ selectedOpportunityId: id }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),

  getSelectedOpportunity: () => {
    const state = get();
    if (!state.selectedOpportunityId) return null;
    return state.opportunities.find((o) => o.id === state.selectedOpportunityId) || null;
  },
}));
