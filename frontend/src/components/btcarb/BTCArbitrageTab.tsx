import { useState, useEffect, useRef } from 'react';

interface ArbLeg {
  ticker: string;
  market_type: string;
  side: string;
  price_cents: number;
  strike?: number;
  lower_bound?: number;
  upper_bound?: number;
}

interface Opportunity {
  id: string;
  range_description: string;
  settlement_time: string;
  legs: ArbLeg[];
  total_cost_cents: number;
  edge_cents: number;
  edge_percent: number;
}

interface Calculation {
  range_ticker: string;
  range_description: string;
  lower_bound: number;
  upper_bound: number;
  range_yes_ask: number | null;
  lower_thresh_ticker: string | null;
  lower_thresh_no_cost: number | null;
  upper_thresh_ticker: string | null;
  upper_thresh_yes_ask: number | null;
  total_cost_cents: number | null;
  edge_cents: number | null;
  is_profitable: boolean;
  reason: string;
  event_date: string;
}

interface SimplifiedMarket {
  ticker: string;
  market_type: string;
  yes_ask: number | null;
  yes_bid: number | null;
  no_ask: number | null;
  no_bid: number | null;
  description: string;
  event_date: string;
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  emoji: string;
}

interface Stats {
  ranges_checked: number;
  thresholds_found: number;
  best_cost: number | null;
  worst_cost: number | null;
  near_misses: number;
  missing_prices: number;
  missing_thresholds: number;
  event_dates: string[];
}

interface EngineStatus {
  is_running: boolean;
  last_scan_at: string | null;
  last_scan_duration_ms: number;
  total_scans: number;
  opportunities_found: number;
  auto_executions: number;
  last_error: string | null;
  config: {
    min_edge_percent: number;
    budget_cents: number;
    auto_trade_enabled: boolean;
    mode: string;
    scan_interval_seconds: number;
  };
  opportunities: Opportunity[];
  market_data: {
    range_markets: SimplifiedMarket[];
    threshold_markets: SimplifiedMarket[];
    event_dates: string[];
  };
  calculations: Calculation[];
  stats: Stats;
  activity_log: LogEntry[];
}

type TabType = 'calculations' | 'markets' | 'log' | 'opportunities';

export function BTCArbitrageTab() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const [execResult, setExecResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<TabType>('calculations');

  const [minEdge, setMinEdge] = useState(3.0);
  const [budgetDollars, setBudgetDollars] = useState(100);
  const [autoTrade, setAutoTrade] = useState(false);
  const [mode, setMode] = useState<'paper' | 'live'>('paper');

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/btc-arb/status');
        const data = await res.json();
        setStatus(data);

        if (data.config) {
          setMinEdge(data.config.min_edge_percent);
          setBudgetDollars(data.config.budget_cents / 100);
          setAutoTrade(data.config.auto_trade_enabled);
          setMode(data.config.mode as 'paper' | 'live');
        }
      } catch (err) {
        console.error('Failed to fetch status:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
    pollRef.current = setInterval(fetchStatus, 1000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const updateConfig = async (updates: Record<string, any>) => {
    try {
      await fetch('/api/btc-arb/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
    } catch (err) {
      console.error('Config update failed:', err);
    }
  };

  const handleMinEdgeChange = (value: number) => {
    setMinEdge(value);
    updateConfig({ min_edge_percent: value });
  };

  const handleBudgetChange = (value: number) => {
    setBudgetDollars(value);
    updateConfig({ budget_cents: value * 100 });
  };

  const handleAutoTradeToggle = (enabled: boolean) => {
    if (enabled && mode === 'live') {
      if (!confirm('Enable LIVE auto-trading with REAL MONEY?')) return;
    }
    setAutoTrade(enabled);
    updateConfig({ auto_trade_enabled: enabled });
  };

  const handleModeChange = (newMode: 'paper' | 'live') => {
    if (newMode === 'live') {
      if (!confirm('Switch to LIVE mode with REAL MONEY?')) return;
    }
    setMode(newMode);
    updateConfig({ mode: newMode });
  };

  const executeOpportunity = async (oppId: string) => {
    setExecuting(oppId);
    setExecResult(null);

    try {
      const res = await fetch(`/api/btc-arb/execute/${oppId}`, { method: 'POST' });
      const data = await res.json();
      setExecResult(data);
    } catch (err) {
      setExecResult({ success: false, error: 'Execution failed' });
    } finally {
      setExecuting(null);
    }
  };

  const getTimeAgo = (iso: string | null) => {
    if (!iso) return '';
    // Ensure ISO string has Z suffix for proper UTC parsing
    const isoWithZ = iso.endsWith('Z') ? iso : iso + 'Z';
    const diff = Date.now() - new Date(isoWithZ).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 0) return 'just now';
    if (seconds < 60) return `${seconds}s ago`;
    return `${Math.floor(seconds / 60)}m ago`;
  };

  const getCostColor = (cost: number | null) => {
    if (cost === null) return 'text-gray-500';
    if (cost < 100) return 'text-green-400';
    if (cost <= 105) return 'text-yellow-400';
    return 'text-gray-400';
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="text-gray-400">Loading arbitrage engine...</div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="p-6 text-center">
        <div className="text-red-400 mb-2">Could not connect to BTC Arbitrage Engine</div>
        <div className="text-gray-500 text-sm">
          Check that the backend is running on port 8001
        </div>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 bg-slate-700 rounded hover:bg-slate-600 text-white"
        >
          Retry
        </button>
      </div>
    );
  }

  const opportunities = status?.opportunities || [];
  const calculations = status?.calculations || [];
  const rangeMarkets = status?.market_data?.range_markets || [];
  const thresholdMarkets = status?.market_data?.threshold_markets || [];
  const activityLog = status?.activity_log || [];
  const stats = status?.stats || {};

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-white">BTC Arbitrage Scanner</h2>
          <p className="text-sm text-gray-400">
            {status?.is_running ? (
              <span className="text-green-400">SCANNING (every {status?.config?.scan_interval_seconds ?? 2}s)</span>
            ) : (
              <span className="text-red-400">STOPPED</span>
            )}
            {status?.last_scan_at && (
              <span className="ml-2">| Last: {getTimeAgo(status.last_scan_at)} ({status.last_scan_duration_ms}ms)</span>
            )}
          </p>
        </div>
        <div className={`px-3 py-1 rounded font-bold text-sm ${mode === 'paper' ? 'bg-blue-600' : 'bg-red-600'} text-white`}>
          {mode === 'paper' ? 'PAPER' : 'LIVE'}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-6 gap-2 bg-slate-800 rounded-lg p-3 text-center">
        <div>
          <div className="text-lg font-bold text-yellow-400">{status?.total_scans || 0}</div>
          <div className="text-xs text-gray-500">Scans</div>
        </div>
        <div>
          <div className="text-lg font-bold text-blue-400">{stats.ranges_checked || 0}</div>
          <div className="text-xs text-gray-500">Ranges</div>
        </div>
        <div>
          <div className="text-lg font-bold text-purple-400">{stats.thresholds_found || 0}</div>
          <div className="text-xs text-gray-500">Thresholds</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${getCostColor(stats.best_cost)}`}>
            {stats.best_cost !== null ? `${stats.best_cost}¢` : '-'}
          </div>
          <div className="text-xs text-gray-500">Best Cost</div>
        </div>
        <div>
          <div className="text-lg font-bold text-orange-400">{stats.near_misses || 0}</div>
          <div className="text-xs text-gray-500">Near Miss</div>
        </div>
        <div>
          <div className="text-lg font-bold text-green-400">{opportunities.length}</div>
          <div className="text-xs text-gray-500">Opps</div>
        </div>
      </div>

      {/* Configuration Row */}
      <div className="bg-slate-800 rounded-lg p-3">
        <div className="grid grid-cols-5 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Min Edge %</label>
            <input
              type="number"
              value={minEdge}
              onChange={(e) => handleMinEdgeChange(parseFloat(e.target.value) || 0)}
              className="w-full bg-slate-700 text-white rounded px-2 py-1 text-sm border border-slate-600"
              step="0.5"
              min="0"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Budget ($)</label>
            <input
              type="number"
              value={budgetDollars}
              onChange={(e) => handleBudgetChange(parseInt(e.target.value) || 0)}
              className="w-full bg-slate-700 text-white rounded px-2 py-1 text-sm border border-slate-600"
              step="10"
              min="1"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Mode</label>
            <select
              value={mode}
              onChange={(e) => handleModeChange(e.target.value as 'paper' | 'live')}
              className="w-full bg-slate-700 text-white rounded px-2 py-1 text-sm border border-slate-600"
            >
              <option value="paper">Paper</option>
              <option value="live">Live</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Auto-Trade</label>
            <button
              onClick={() => handleAutoTradeToggle(!autoTrade)}
              className={`w-full py-1 rounded text-sm font-bold ${
                autoTrade ? 'bg-green-600 text-white' : 'bg-slate-600 text-gray-300'
              }`}
            >
              {autoTrade ? 'ON' : 'OFF'}
            </button>
          </div>
          <div className="flex items-end">
            <div className="text-xs text-gray-500">
              Events: {(stats.event_dates || []).join(', ') || 'None'}
            </div>
          </div>
        </div>
      </div>

      {/* Execution result */}
      {execResult && (
        <div className={`p-3 rounded-lg text-sm ${execResult.success ? 'bg-green-900/50 border border-green-500' : 'bg-red-900/50 border border-red-500'}`}>
          <span className="font-bold">{execResult.success ? 'Trade Executed!' : 'Execution Failed'}</span>
          {execResult.success && <span className="ml-2">{execResult.contracts} contracts | Profit: ${(execResult.profit_cents / 100).toFixed(2)}</span>}
          {execResult.error && <span className="ml-2 text-red-300">{execResult.error}</span>}
          <button onClick={() => setExecResult(null)} className="ml-3 text-blue-400 underline">Dismiss</button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-700">
        {[
          { key: 'calculations', label: `Calculations (${calculations.length})` },
          { key: 'markets', label: `Markets (${rangeMarkets.length}/${thresholdMarkets.length})` },
          { key: 'log', label: `Log (${activityLog.length})` },
          { key: 'opportunities', label: `Opportunities (${opportunities.length})` }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as TabType)}
            className={`px-4 py-2 text-sm font-medium ${
              activeTab === tab.key
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-slate-800 rounded-lg p-4 max-h-96 overflow-y-auto">
        {activeTab === 'calculations' && (
          <div className="space-y-2">
            {calculations.length === 0 ? (
              <div className="text-gray-500 text-center py-4">No calculations yet - waiting for scan</div>
            ) : (
              calculations.map((calc, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded border ${
                    calc.is_profitable
                      ? 'bg-green-900/30 border-green-500'
                      : calc.total_cost_cents !== null && calc.total_cost_cents <= 105
                      ? 'bg-yellow-900/20 border-yellow-600'
                      : 'bg-slate-700/50 border-slate-600'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-medium text-white">{calc.range_description}</span>
                      <span className="text-xs text-gray-400 ml-2">{calc.event_date}</span>
                    </div>
                    <div className="text-right">
                      <span className={`font-bold ${getCostColor(calc.total_cost_cents)}`}>
                        {calc.total_cost_cents !== null ? `${calc.total_cost_cents}¢` : '-'}
                      </span>
                      {calc.edge_cents !== null && (
                        <span className="text-xs text-gray-400 ml-2">
                          ({calc.edge_cents > 0 ? '+' : ''}{calc.edge_cents}¢)
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 mt-1 font-mono">
                    Range: {calc.range_yes_ask ?? '-'}¢ + LowerNO: {calc.lower_thresh_no_cost ?? '-'}¢ + UpperYES: {calc.upper_thresh_yes_ask ?? '-'}¢
                  </div>
                  <div className={`text-xs mt-1 ${calc.is_profitable ? 'text-green-400' : 'text-gray-500'}`}>
                    {calc.reason}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'markets' && (
          <div className="grid grid-cols-2 gap-4">
            {/* Range Markets */}
            <div>
              <h4 className="text-sm font-bold text-blue-400 mb-2">KXBTC Range Markets ({rangeMarkets.length})</h4>
              <div className="space-y-1 max-h-72 overflow-y-auto">
                {rangeMarkets.map((mkt, idx) => (
                  <div key={idx} className="flex justify-between text-xs bg-slate-700/50 px-2 py-1 rounded">
                    <span className="text-gray-300 truncate" title={mkt.ticker}>{mkt.description}</span>
                    <span className="text-yellow-400">{mkt.yes_ask ?? '-'}¢</span>
                  </div>
                ))}
                {rangeMarkets.length === 0 && <div className="text-gray-500 text-center py-2">No range markets</div>}
              </div>
            </div>
            {/* Threshold Markets */}
            <div>
              <h4 className="text-sm font-bold text-purple-400 mb-2">KXBTCD Threshold Markets ({thresholdMarkets.length})</h4>
              <div className="space-y-1 max-h-72 overflow-y-auto">
                {thresholdMarkets.map((mkt, idx) => (
                  <div key={idx} className="flex justify-between text-xs bg-slate-700/50 px-2 py-1 rounded">
                    <span className="text-gray-300 truncate" title={mkt.ticker}>{mkt.description}</span>
                    <span className="text-green-400">{mkt.yes_bid ?? '-'}¢/{mkt.yes_ask ?? '-'}¢</span>
                  </div>
                ))}
                {thresholdMarkets.length === 0 && <div className="text-gray-500 text-center py-2">No threshold markets</div>}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'log' && (
          <div className="space-y-1 font-mono text-xs">
            {activityLog.length === 0 ? (
              <div className="text-gray-500 text-center py-4">No log entries yet</div>
            ) : (
              activityLog.map((entry, idx) => (
                <div key={idx} className="flex gap-2">
                  <span className="text-gray-600">{getTimeAgo(entry.timestamp)}</span>
                  <span className={entry.level === 'ERROR' ? 'text-red-400' : entry.level === 'WARNING' ? 'text-yellow-400' : 'text-gray-300'}>
                    {entry.message}
                  </span>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'opportunities' && (
          <div className="space-y-3">
            {opportunities.length === 0 ? (
              <div className="text-gray-500 text-center py-4">
                No opportunities above {minEdge}% edge
                {stats.near_misses > 0 && (
                  <div className="text-yellow-500 mt-1">{stats.near_misses} near-misses (cost 100-105¢)</div>
                )}
              </div>
            ) : (
              opportunities.map((opp, idx) => (
                <div key={opp.id} className={`p-3 rounded border-2 ${idx === 0 ? 'border-green-500 bg-green-900/20' : 'border-slate-600 bg-slate-700/50'}`}>
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="font-bold text-white">{idx === 0 && '🏆 '}{opp.range_description}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-xl font-bold text-green-400">{opp.edge_percent.toFixed(1)}%</span>
                      <p className="text-xs text-gray-400">{opp.edge_cents}¢ per set</p>
                    </div>
                  </div>

                  <div className="bg-slate-800 rounded p-2 mb-2 text-xs font-mono">
                    {opp.legs.map((leg, i) => (
                      <div key={i} className="flex justify-between text-gray-300">
                        <span>{leg.side.toUpperCase()} {leg.market_type === 'range' ? 'Range' : `≥$${leg.strike?.toLocaleString()}`}</span>
                        <span className="text-yellow-400">{leg.price_cents}¢</span>
                      </div>
                    ))}
                    <div className="border-t border-slate-600 mt-1 pt-1 flex justify-between font-bold text-white">
                      <span>Total → Payout</span>
                      <span>{opp.total_cost_cents}¢ → 100¢</span>
                    </div>
                  </div>

                  <button
                    onClick={() => executeOpportunity(opp.id)}
                    disabled={executing === opp.id || autoTrade}
                    className={`w-full py-2 rounded text-sm font-bold ${
                      autoTrade ? 'bg-gray-600 cursor-not-allowed text-gray-400' : mode === 'paper' ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-red-600 hover:bg-red-700 text-white'
                    } disabled:opacity-50`}
                  >
                    {executing === opp.id ? 'Executing...' : autoTrade ? '(Auto-trade enabled)' : `Execute (${mode})`}
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div className="text-xs text-gray-500 text-center">
        Auto-executions: {status?.auto_executions || 0} | Missing prices: {stats.missing_prices || 0} | Missing thresholds: {stats.missing_thresholds || 0}
        {status?.last_error && <span className="text-red-400 ml-2">| Error: {status.last_error}</span>}
      </div>
    </div>
  );
}

export default BTCArbitrageTab;
