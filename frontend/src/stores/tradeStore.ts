import { create } from 'zustand';
import type { TradeResult, SizingSuggestions, TradeDetails } from '../types';

interface TradeState {
  isTrading: boolean;
  tradeModalOpen: boolean;
  selectedOpportunityId: string | null;
  positionSize: number;
  sizingSuggestions: SizingSuggestions | null;
  tradeDetails: TradeDetails | null;
  lastTradeResult: TradeResult | null;
  error: string | null;

  openTradeModal: (opportunityId: string) => void;
  closeTradeModal: () => void;
  setPositionSize: (size: number) => void;
  setSizingSuggestions: (suggestions: SizingSuggestions) => void;
  setTradeDetails: (details: TradeDetails | null) => void;
  setTrading: (isTrading: boolean) => void;
  setTradeResult: (result: TradeResult) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useTradeStore = create<TradeState>((set) => ({
  isTrading: false,
  tradeModalOpen: false,
  selectedOpportunityId: null,
  positionSize: 0,
  sizingSuggestions: null,
  tradeDetails: null,
  lastTradeResult: null,
  error: null,

  openTradeModal: (opportunityId) =>
    set({
      tradeModalOpen: true,
      selectedOpportunityId: opportunityId,
      positionSize: 0,
      tradeDetails: null,
      lastTradeResult: null,
      error: null,
    }),

  closeTradeModal: () =>
    set({
      tradeModalOpen: false,
      selectedOpportunityId: null,
      positionSize: 0,
      tradeDetails: null,
      error: null,
    }),

  setPositionSize: (positionSize) => set({ positionSize }),

  setSizingSuggestions: (sizingSuggestions) => set({ sizingSuggestions }),

  setTradeDetails: (tradeDetails) => set({ tradeDetails }),

  setTrading: (isTrading) => set({ isTrading }),

  setTradeResult: (lastTradeResult) =>
    set({ lastTradeResult, isTrading: false }),

  setError: (error) => set({ error, isTrading: false }),

  reset: () =>
    set({
      isTrading: false,
      tradeModalOpen: false,
      selectedOpportunityId: null,
      positionSize: 0,
      sizingSuggestions: null,
      tradeDetails: null,
      lastTradeResult: null,
      error: null,
    }),
}));
