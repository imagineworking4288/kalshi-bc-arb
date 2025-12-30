import { create } from 'zustand';
import type { Opportunity } from '../types';

interface OpportunityState {
  opportunities: Opportunity[];
  spotPrice: number | null;
  loading: boolean;
  error: string | null;

  setOpportunities: (opps: Opportunity[]) => void;
  setSpotPrice: (price: number | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useOpportunityStore = create<OpportunityState>((set) => ({
  opportunities: [],
  spotPrice: null,
  loading: false,
  error: null,

  setOpportunities: (opportunities) => set({ opportunities, error: null }),
  setSpotPrice: (spotPrice) => set({ spotPrice }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error })
}));
