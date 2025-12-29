import { useEffect } from 'react';
import { useOpportunityStore } from '../stores/opportunityStore';
import { wsService } from '../services/websocket';
import type { SpotPrices, Opportunity } from '../types';

interface ConnectionStatus {
  status: 'connected' | 'disconnected' | 'error' | 'failed';
}

export function useWebSocket() {
  const { setOpportunities, setSpotPrices, setConnectionStatus } =
    useOpportunityStore();

  useEffect(() => {
    // Connect WebSocket
    wsService.connect();

    // Handle connection status
    const unsubConnection = wsService.subscribe(
      'connection',
      (data: unknown) => {
        const { status } = data as ConnectionStatus;
        setConnectionStatus(status);
      }
    );

    // Handle spot price updates
    const unsubPrices = wsService.subscribe('spot_prices', (data: unknown) => {
      setSpotPrices(data as SpotPrices);
    });

    // Handle opportunity updates
    const unsubOpps = wsService.subscribe('opportunities', (data: unknown) => {
      // Transform the data to match our Opportunity type
      const opps = data as Array<{
        id: string;
        asset: string;
        threshold_strike: number;
        threshold_direction: string;
        net_profit_pct: number;
        max_liquidity_usd: number;
        spot_price: number | null;
        spot_relation: string;
        score: number;
        trade_direction: string;
        settlement_time: string;
      }>;

      // Only update if we have data (WebSocket provides partial updates)
      if (opps && opps.length > 0) {
        // This is a partial update, merge with existing
        // For now, we'll just use the REST API polling
      }
    });

    return () => {
      unsubConnection();
      unsubPrices();
      unsubOpps();
      wsService.disconnect();
    };
  }, [setOpportunities, setSpotPrices, setConnectionStatus]);
}
