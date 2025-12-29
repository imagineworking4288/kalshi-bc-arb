import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AlertSettings, RiskSettings } from '../types';

interface SettingsState {
  environment: 'demo' | 'production';
  alertSettings: AlertSettings;
  riskSettings: RiskSettings;

  setEnvironment: (env: 'demo' | 'production') => void;
  setAlertSettings: (settings: Partial<AlertSettings>) => void;
  setRiskSettings: (settings: Partial<RiskSettings>) => void;
  resetToDefaults: () => void;
}

const defaultAlertSettings: AlertSettings = {
  minProfitPct: 3,
  minLiquidityUsd: 100,
  visualHighlight: true,
  audioEnabled: true,
  audioSound: 'chime',
  audioVolume: 80,
  browserNotifications: false,
};

const defaultRiskSettings: RiskSettings = {
  maxPositionPerMarket: 500,
  maxTotalExposure: 2000,
  maxDailyLoss: 200,
  maxSingleTrade: 250,
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      environment: 'demo',
      alertSettings: defaultAlertSettings,
      riskSettings: defaultRiskSettings,

      setEnvironment: (environment) => set({ environment }),

      setAlertSettings: (settings) =>
        set((state) => ({
          alertSettings: { ...state.alertSettings, ...settings },
        })),

      setRiskSettings: (settings) =>
        set((state) => ({
          riskSettings: { ...state.riskSettings, ...settings },
        })),

      resetToDefaults: () =>
        set({
          alertSettings: defaultAlertSettings,
          riskSettings: defaultRiskSettings,
        }),
    }),
    {
      name: 'kalshi-arb-settings',
    }
  )
);
