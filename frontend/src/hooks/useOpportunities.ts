import { useEffect, useCallback } from 'react';
import { useOpportunityStore } from '../stores/opportunityStore';
import { api } from '../services/api';

export function useOpportunities() {
  const {
    opportunities,
    spotPrices,
    isLoading,
    error,
    setOpportunities,
    setSpotPrices,
    setBalance,
    setLoading,
    setError,
  } = useOpportunityStore();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [oppsRes, pricesRes, balanceRes] = await Promise.all([
        api.getOpportunities(),
        api.getSpotPrices(),
        api.getBalance().catch(() => null),
      ]);

      setOpportunities(oppsRes.opportunities);
      setSpotPrices(pricesRes.prices);
      if (balanceRes) {
        setBalance(balanceRes);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [setOpportunities, setSpotPrices, setBalance, setLoading, setError]);

  // Initial fetch and polling
  useEffect(() => {
    fetchData();

    // Poll every 30 seconds as fallback to WebSocket
    const interval = setInterval(fetchData, 30000);

    return () => clearInterval(interval);
  }, [fetchData]);

  return {
    opportunities,
    spotPrices,
    isLoading,
    error,
    refresh: fetchData,
  };
}
