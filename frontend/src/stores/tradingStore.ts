import { create } from 'zustand';
import type { TradingMode, Balance, Position, Opportunity } from '../types';

interface TradingState {
  mode: TradingMode;
  balance: Balance | null;
  positions: Position[];
  selectedOpportunity: Opportunity | null;
  executeModalOpen: boolean;

  setMode: (mode: TradingMode) => void;
  setBalance: (balance: Balance) => void;
  setPositions: (positions: Position[]) => void;
  openExecuteModal: (opp: Opportunity) => void;
  closeExecuteModal: () => void;
}

export const useTradingStore = create<TradingState>((set) => ({
  mode: 'paper',
  balance: null,
  positions: [],
  selectedOpportunity: null,
  executeModalOpen: false,

  setMode: (mode) => set({ mode }),
  setBalance: (balance) => set({ balance }),
  setPositions: (positions) => set({ positions }),
  openExecuteModal: (opp) => set({ executeModalOpen: true, selectedOpportunity: opp }),
  closeExecuteModal: () => set({ executeModalOpen: false, selectedOpportunity: null })
}));
