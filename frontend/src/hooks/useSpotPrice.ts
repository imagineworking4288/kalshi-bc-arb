import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

interface SpotPriceData {
  price: number;
  source: string;
  timestamp: string;
  isLive: boolean;
}

interface UseSpotPriceResult {
  data: SpotPriceData | null;
  error: string | null;
  isLoading: boolean;
  refresh: () => void;
}

const POLL_INTERVAL = 15000; // 15 seconds - safe for rate limits
const STALE_THRESHOLD = 60000; // 60 seconds - consider data stale

export function useSpotPrice(): UseSpotPriceResult {
  const [data, setData] = useState<SpotPriceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchPrice = useCallback(async () => {
    try {
      const result = await api.getSpotPrice();
      const timestamp = new Date(result.timestamp);
      const age = Date.now() - timestamp.getTime();

      setData({
        price: result.price,
        source: result.source,
        timestamp: result.timestamp,
        isLive: age < STALE_THRESHOLD
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch price');
      // Keep old data if available, just mark as not live
      if (data) {
        setData({ ...data, isLive: false });
      }
    } finally {
      setIsLoading(false);
    }
  }, [data]);

  useEffect(() => {
    fetchPrice();
    const interval = setInterval(fetchPrice, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  return { data, error, isLoading, refresh: fetchPrice };
}
