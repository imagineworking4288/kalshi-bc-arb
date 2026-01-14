/**
 * usePredictions hook for weather prediction data.
 *
 * Features:
 * - Auto-refresh every 5 minutes
 * - Manual refresh function
 * - Loading/error/data states
 * - Stale data indicator
 * - Cache status tracking
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../services/api';

// Types
export interface ForecastData {
  city: string;
  forecast_high: number;
  forecast_low: number;
  weather_pattern: string;
  short_forecast: string;
  source: string;
  fetched_at: string;
  cached: boolean;
  cache_age_seconds: number;
}

export interface BracketPrediction {
  ticker: string;
  label: string;
  model_probability: number;
  market_implied_probability: number;
  probability_edge: number;
  yes_price_cents: number | null;
  no_price_cents: number | null;
  yes_ev_after_fee: number;
  no_ev_after_fee: number;
  recommended_action: string;
  recommended_side: string | null;
  recommended_contracts: number;
  kelly_fraction: number;
  has_existing_position: boolean;
  position_conflict: boolean;
  existing_side?: 'yes' | 'no' | null;
  confidence: number;
}

export interface PredictionData {
  city: string;
  event_ticker: string;
  forecast: ForecastData;
  brackets: BracketPrediction[];
  total_probability: number;
  has_opportunities: boolean;
  best_opportunity: BracketPrediction | null;
  warnings: string[];
  generated_at: string;
}

export interface SupportedCity {
  code: string;
  latitude: number;
  longitude: number;
  timezone: string;
}

export interface UsePredictionsResult {
  data: PredictionData | null;
  error: string | null;
  isLoading: boolean;
  isStale: boolean;
  dataSource: string | null;
  cacheAge: number;
  refresh: () => Promise<void>;
  forceRefresh: () => Promise<void>;
}

export interface UseCitiesResult {
  cities: SupportedCity[];
  isLoading: boolean;
  error: string | null;
}

// Constants
const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes
const STALE_THRESHOLD = 30 * 60 * 1000; // 30 minutes - data is stale

/**
 * Hook to fetch and manage prediction data for a city.
 */
export function usePredictions(city: string): UsePredictionsResult {
  const [data, setData] = useState<PredictionData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dataSource, setDataSource] = useState<string | null>(null);
  const [cacheAge, setCacheAge] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchPredictions = useCallback(async (forceRefresh = false) => {
    if (!city) {
      setError('No city specified');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.getPredictions(city, forceRefresh);
      setData(result);
      setDataSource(result.forecast.source);
      setCacheAge(result.forecast.cache_age_seconds);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch predictions';
      setError(message);
      // Keep old data if available
      if (data) {
        setCacheAge(prev => prev + POLL_INTERVAL / 1000);
      }
    } finally {
      setIsLoading(false);
    }
  }, [city, data]);

  // Initial fetch and polling
  useEffect(() => {
    fetchPredictions(false);

    // Set up polling
    intervalRef.current = setInterval(() => {
      fetchPredictions(false);
    }, POLL_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [city]); // Re-fetch when city changes

  const refresh = useCallback(async () => {
    await fetchPredictions(false);
  }, [fetchPredictions]);

  const forceRefresh = useCallback(async () => {
    await fetchPredictions(true);
  }, [fetchPredictions]);

  // Calculate staleness
  const isStale = data ? (cacheAge * 1000) > STALE_THRESHOLD : false;

  return {
    data,
    error,
    isLoading,
    isStale,
    dataSource,
    cacheAge,
    refresh,
    forceRefresh,
  };
}

/**
 * Hook to fetch supported cities.
 */
export function useSupportedCities(): UseCitiesResult {
  const [cities, setCities] = useState<SupportedCity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchCities() {
      try {
        const result = await api.getSupportedCities();
        setCities(result.cities);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch cities');
      } finally {
        setIsLoading(false);
      }
    }

    fetchCities();
  }, []);

  return { cities, isLoading, error };
}

/**
 * Hook for prediction system status.
 */
export function usePredictionStatus() {
  const [status, setStatus] = useState<{
    circuits: { nws: string; open_meteo: string };
    supported_cities: string[];
    cache_entries: number;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const result = await api.getPredictionStatus();
      setStatus(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch status');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return { status, isLoading, error, refresh: fetchStatus };
}

export default usePredictions;
