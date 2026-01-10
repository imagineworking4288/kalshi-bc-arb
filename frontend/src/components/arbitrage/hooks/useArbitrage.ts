/**
 * React hooks for arbitrage data fetching and WebSocket connection.
 * Provides real-time updates for opportunities, orderbooks, and risk metrics.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = '/api';
const WS_BASE = `ws://${window.location.hostname}:8001`;

// ============ Types ============

export interface ArbitrageLeg {
  ticker: string;
  side: 'yes' | 'no';
  action: 'buy' | 'sell';
  quantity: number;
  price_cents: number;
  fee_cents: number;
  bracket_label: string;
}

export interface ArbitrageOpportunity {
  id: string;
  event_ticker: string;
  event_title: string;
  strategy: string;
  legs: ArbitrageLeg[];
  total_cost_cents: number;
  total_fees_cents: number;
  expected_profit_cents: number;
  profit_after_fees_cents: number;
  roi_percent: number;
  confidence: number;
  warnings: string[];
  is_stale: boolean;
  calculated_at: string;
  expires_at?: string;
  // Additional fields from existing API
  asset?: string;
  settlement_time?: string;
  threshold_ticker?: string;
  threshold_title?: string;
  threshold_strike?: number;
  bracket_count?: number;
  cost_per_set?: number;
  fees_per_set?: number;
  profit_per_set?: number;
  net_profit_pct?: number;
  max_contracts?: number;
  max_liquidity_usd?: number;
  spot_price?: number | null;
  brackets?: Array<{
    ticker: string;
    low: number;
    high: number;
    yes_price: number;
  }>;
}

export interface OrderbookLevel {
  price_cents: number;
  quantity: number;
}

export interface Orderbook {
  ticker: string;
  yes_bids: OrderbookLevel[];
  no_bids: OrderbookLevel[];
  yes_ask: number | null;
  no_ask: number | null;
  timestamp: string;
  is_stale: boolean;
}

export interface CircuitBreakerStatus {
  can_trade: boolean;
  tripped: boolean;
  trip_reason: string | null;
  cooldown_until: string | null;
  daily_pnl_cents: number;
  total_position: number;
  consecutive_losses: number;
  win_rate: number;
  drawdown_percent: number;
  warnings: string[];
}

export interface RiskDashboard {
  timestamp: string;
  trading_mode: string;
  balance_cents: number;
  daily_pnl_cents: number;
  total_pnl_cents: number;
  unrealized_pnl_cents: number;
  total_position: number;
  trades_today: number;
  wins_today: number;
  losses_today: number;
  win_rate: number;
  drawdown_percent: number;
  circuit_breaker: CircuitBreakerStatus;
  positions?: Array<{
    ticker: string;
    side: string;
    quantity: number;
    avg_cost_cents: number;
    unrealized_pnl_cents: number;
    current_price: number | null;
  }>;
}

export interface ExecutionResult {
  execution_id: string;
  trade_id?: string;
  status: string;
  success: boolean;
  fully_filled: boolean;
  total_cost_cents: number;
  total_fees_cents: number;
  profit_cents: number | null;
  expected_profit?: number;
  expected_profit_pct?: number;
  expected_payout?: number;
  errors: string[];
  warnings: string[];
  trading_mode: string;
  paper_mode?: boolean;
  message?: string;
  orders?: Array<{
    ticker: string;
    contracts: number;
    price: number;
    fee: number;
  }>;
}

// ============ API Functions ============

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// ============ Hooks ============

/**
 * Hook for fetching and managing arbitrage opportunities
 */
export function useOpportunities(minProfitPercent: number = 1.0) {
  const [opportunities, setOpportunities] = useState<ArbitrageOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [tradingMode, setTradingMode] = useState<string>('paper');

  const fetchOpportunities = useCallback(async () => {
    try {
      const data = await fetchApi<{
        opportunities: ArbitrageOpportunity[];
        count: number;
        paper_mode: boolean;
      }>(`/opportunities?min_profit=${minProfitPercent}`);

      // Transform existing API response to match expected format
      const transformedOpps = data.opportunities.map(opp => ({
        ...opp,
        event_ticker: opp.id || opp.event_ticker,
        event_title: opp.threshold_title || opp.event_title || '',
        total_cost_cents: Math.round((opp.cost_per_set || 0) * 100),
        total_fees_cents: (opp.fees_per_set || 0) * 100,
        expected_profit_cents: (opp.profit_per_set || 0) * 100,
        profit_after_fees_cents: (opp.profit_per_set || 0) * 100,
        roi_percent: opp.net_profit_pct || 0,
        legs: opp.brackets?.map(b => ({
          ticker: b.ticker,
          side: 'yes' as const,
          action: 'buy' as const,
          quantity: 1,
          price_cents: Math.round(b.yes_price * 100),
          fee_cents: 0,
          bracket_label: `${b.low}-${b.high}`
        })) || [],
        strategy: 'all_yes',
        confidence: 1.0,
        warnings: [],
        is_stale: false,
        calculated_at: new Date().toISOString(),
      }));

      setOpportunities(transformedOpps);
      setLastUpdated(new Date().toISOString());
      setTradingMode(data.paper_mode ? 'paper' : 'live');
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch opportunities');
    } finally {
      setLoading(false);
    }
  }, [minProfitPercent]);

  useEffect(() => {
    fetchOpportunities();
    const interval = setInterval(fetchOpportunities, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchOpportunities]);

  return {
    opportunities,
    loading,
    error,
    lastUpdated,
    tradingMode,
    refresh: fetchOpportunities,
  };
}

/**
 * Hook for WebSocket connection with auto-reconnect
 */
export function useWebSocket(eventTickers: string[] = []) {
  const [connected, setConnected] = useState(false);
  const [orderbooks, setOrderbooks] = useState<Record<string, Orderbook>>({});
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const eventTickersRef = useRef(eventTickers);

  // Keep ref updated
  useEffect(() => {
    eventTickersRef.current = eventTickers;
  }, [eventTickers]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(`${WS_BASE}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttempts.current = 0;

        // Subscribe to events
        if (eventTickersRef.current.length > 0) {
          ws.send(JSON.stringify({
            type: 'subscribe',
            event_tickers: eventTickersRef.current,
          }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);

          switch (message.type) {
            case 'orderbook_update':
              setOrderbooks(prev => ({
                ...prev,
                [message.ticker]: message.orderbook,
              }));
              break;
            case 'pong':
              // Heartbeat received
              break;
            case 'connected':
            case 'subscribed':
              // Connection confirmed
              break;
          }
        } catch (err) {
          console.error('WebSocket message error:', err);
        }
      };

      ws.onclose = () => {
        setConnected(false);

        // Reconnect with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;

        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (err) {
      console.error('WebSocket connection error:', err);
      setConnected(false);
    }
  }, []);

  // Heartbeat
  useEffect(() => {
    const heartbeat = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    return () => clearInterval(heartbeat);
  }, []);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  // Update subscriptions when eventTickers change
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN && eventTickers.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        event_tickers: eventTickers,
      }));
    }
  }, [eventTickers]);

  return {
    connected,
    orderbooks,
    lastMessage,
    reconnect: connect,
  };
}

/**
 * Hook for risk dashboard data
 */
export function useRiskDashboard() {
  const [risk, setRisk] = useState<RiskDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRisk = useCallback(async () => {
    try {
      // Use existing endpoints to build risk data
      const [balanceRes, summaryRes, circuitRes] = await Promise.all([
        fetchApi<any>('/balance').catch(() => ({ available_balance: 0, paper_mode: true })),
        fetchApi<any>('/paper/summary').catch(() => ({})),
        fetchApi<any>('/circuit-breaker/status').catch(() => ({
          can_trade: true,
          tripped: false,
          daily_loss_cents: 0,
          total_exposure_cents: 0,
        })),
      ]);

      const riskData: RiskDashboard = {
        timestamp: new Date().toISOString(),
        trading_mode: balanceRes.paper_mode ? 'paper' : 'live',
        balance_cents: Math.round((balanceRes.available_balance || 0) * 100),
        daily_pnl_cents: Math.round((summaryRes.total_pnl || 0) * 100),
        total_pnl_cents: Math.round((summaryRes.total_pnl || 0) * 100),
        unrealized_pnl_cents: Math.round((summaryRes.open_positions_value || 0) * 100),
        total_position: summaryRes.total_trades || 0,
        trades_today: summaryRes.total_trades || 0,
        wins_today: 0,
        losses_today: 0,
        win_rate: 0.5,
        drawdown_percent: 0,
        circuit_breaker: {
          can_trade: circuitRes.can_trade ?? true,
          tripped: circuitRes.tripped ?? false,
          trip_reason: circuitRes.reason || null,
          cooldown_until: circuitRes.cooldown_until || null,
          daily_pnl_cents: circuitRes.daily_loss_cents || 0,
          total_position: circuitRes.total_exposure_cents || 0,
          consecutive_losses: 0,
          win_rate: 0.5,
          drawdown_percent: 0,
          warnings: circuitRes.warnings || [],
        },
      };

      setRisk(riskData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch risk data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRisk();
    const interval = setInterval(fetchRisk, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, [fetchRisk]);

  const resetCircuitBreaker = async () => {
    try {
      await fetchApi('/circuit-breaker/reset', { method: 'POST' });
      await fetchRisk();
    } catch (err) {
      throw err;
    }
  };

  const tripCircuitBreaker = async (reason: string = 'Manual trip') => {
    try {
      await fetchApi(`/circuit-breaker/trip?reason=${encodeURIComponent(reason)}`, { method: 'POST' });
      await fetchRisk();
    } catch (err) {
      throw err;
    }
  };

  return {
    risk,
    loading,
    error,
    refresh: fetchRisk,
    resetCircuitBreaker,
    tripCircuitBreaker,
  };
}

/**
 * Hook for executing trades
 */
export function useExecution() {
  const [executing, setExecuting] = useState(false);
  const [lastResult, setLastResult] = useState<ExecutionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const execute = async (
    opportunityId: string,
    numContracts: number = 1,
    _confirmLive: boolean = false
  ): Promise<ExecutionResult> => {
    setExecuting(true);
    setError(null);

    try {
      const result = await fetchApi<any>('/execute', {
        method: 'POST',
        body: JSON.stringify({
          opportunity_id: opportunityId,
          num_contracts: numContracts,
        }),
      });

      // Transform to ExecutionResult format
      const executionResult: ExecutionResult = {
        execution_id: result.trade_id || '',
        trade_id: result.trade_id,
        status: result.status,
        success: result.status === 'success',
        fully_filled: result.status === 'success',
        total_cost_cents: Math.round((result.total_cost || 0) * 100),
        total_fees_cents: Math.round((result.total_fees || 0) * 100),
        profit_cents: result.expected_profit ? Math.round(result.expected_profit * 100) : null,
        expected_profit: result.expected_profit,
        expected_profit_pct: result.expected_profit_pct,
        expected_payout: result.expected_payout,
        errors: result.status === 'failed' ? [result.message || 'Unknown error'] : [],
        warnings: result.paper_mode ? ['Paper trading - no real orders placed'] : [],
        trading_mode: result.paper_mode ? 'paper' : 'live',
        paper_mode: result.paper_mode,
        message: result.message,
        orders: result.orders,
      };

      setLastResult(executionResult);
      return executionResult;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Execution failed';
      setError(message);
      throw err;
    } finally {
      setExecuting(false);
    }
  };

  const clearResult = () => {
    setLastResult(null);
    setError(null);
  };

  return {
    execute,
    executing,
    lastResult,
    error,
    clearResult,
  };
}

/**
 * Hook for trading mode management
 */
export function useTradingMode() {
  const [mode, setModeState] = useState<'paper' | 'live'>('paper');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial mode
  useEffect(() => {
    fetchApi<{ paper_mode: boolean }>('/config')
      .then(config => setModeState(config.paper_mode ? 'paper' : 'live'))
      .catch(() => setModeState('paper'));
  }, []);

  const setMode = async (newMode: 'paper' | 'live', _confirmLive?: string) => {
    setLoading(true);
    setError(null);

    try {
      const result = await fetchApi<{ mode: string }>('/orchestrator/mode', {
        method: 'POST',
        body: JSON.stringify({
          mode: newMode,
        }),
      });

      setModeState(result.mode as 'paper' | 'live');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to change mode');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return {
    mode,
    setMode,
    loading,
    error,
  };
}

/**
 * Hook for system status
 */
export function useSystemStatus() {
  const [status, setStatus] = useState<{
    status: string;
    websocket_connected: boolean;
    exchange_active: boolean;
    trading_mode: string;
    warnings: string[];
  } | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const [configRes, orchRes] = await Promise.all([
        fetchApi<any>('/config').catch(() => ({})),
        fetchApi<any>('/orchestrator/status').catch(() => ({ is_running: false })),
      ]);

      setStatus({
        status: orchRes.is_running ? 'healthy' : 'degraded',
        websocket_connected: true, // Will be updated by useWebSocket
        exchange_active: true,
        trading_mode: configRes.paper_mode ? 'paper' : 'live',
        warnings: [],
      });
    } catch (err) {
      setStatus({
        status: 'error',
        websocket_connected: false,
        exchange_active: false,
        trading_mode: 'paper',
        warnings: ['Failed to fetch system status'],
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return {
    status,
    loading,
    refresh: fetchStatus,
  };
}

/**
 * Hook for positions
 */
export function usePositions() {
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPositions = useCallback(async () => {
    try {
      const data = await fetchApi<{ positions: any[] }>('/positions');
      setPositions(data.positions || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch positions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000);
    return () => clearInterval(interval);
  }, [fetchPositions]);

  return {
    positions,
    loading,
    error,
    refresh: fetchPositions,
  };
}
