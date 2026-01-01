import React, { useState, useEffect, useRef } from 'react';

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
}

export function BTCArbitrageTab() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const [execResult, setExecResult] = useState<any>(null);

  const [minEdge, setMinEdge] = useState(3.0);
  const [budgetDollars, setBudgetDollars] = useState(100);
  const [autoTrade, setAutoTrade] = useState(false);
  const [mode, setMode] = useState<'paper' | 'live'>('paper');

  const pollRef = useRef<NodeJS.Timeout | null>(null);

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
      if (!confirm('⚠️ Enable LIVE auto-trading with REAL MONEY?')) return;
    }
    setAutoTrade(enabled);
    updateConfig({ auto_trade_enabled: enabled });
  };

  const handleModeChange = (newMode: 'paper' | 'live') => {
    if (newMode === 'live') {
      if (!confirm('⚠️ Switch to LIVE mode with REAL MONEY?')) return;
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
    const diff = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    return `${Math.floor(seconds / 60)}m ago`;
  };

  if (loading) return <div className="p-6 text-gray-400">Loading arbitrage engine...</div>;

  const opportunities = status?.opportunities || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white">BTC Arbitrage Scanner</h2>
          <p className="text-sm text-gray-400">
            {status?.is_running ? (
              <span className="text-green-400">● SCANNING (every {status.config.scan_interval_seconds}s)</span>
            ) : (
              <span className="text-red-400">○ STOPPED</span>
            )}
            {status?.last_scan_at && (
              <span className="ml-2">| Last: {getTimeAgo(status.last_scan_at)} ({status.last_scan_duration_ms}ms)</span>
            )}
          </p>
        </div>
        <div className={`px-4 py-2 rounded-lg font-bold text-white ${mode === 'paper' ? 'bg-blue-600' : 'bg-red-600'}`}>
          {mode === 'paper' ? '📝 PAPER' : '💰 LIVE'}
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-slate-800 rounded-lg p-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Min Edge %</label>
            <input
              type="number"
              value={minEdge}
              onChange={(e) => handleMinEdgeChange(parseFloat(e.target.value) || 0)}
              className="w-full bg-slate-700 text-white rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
              step="0.5"
              min="0"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Budget ($)</label>
            <input
              type="number"
              value={budgetDollars}
              onChange={(e) => handleBudgetChange(parseInt(e.target.value) || 0)}
              className="w-full bg-slate-700 text-white rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
              step="10"
              min="1"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Mode</label>
            <select
              value={mode}
              onChange={(e) => handleModeChange(e.target.value as 'paper' | 'live')}
              className="w-full bg-slate-700 text-white rounded px-3 py-2 border border-slate-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="paper">Paper</option>
              <option value="live">Live</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Auto-Trade</label>
            <button
              onClick={() => handleAutoTradeToggle(!autoTrade)}
              className={`w-full py-2 rounded font-bold transition-colors ${
                autoTrade ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-slate-600 hover:bg-slate-500 text-gray-300'
              }`}
            >
              {autoTrade ? '✓ ON' : 'OFF'}
            </button>
          </div>

          <div className="flex items-end">
            <div className="text-center w-full">
              <div className="text-2xl font-bold text-yellow-400">{status?.total_scans || 0}</div>
              <div className="text-xs text-gray-400">Total Scans</div>
            </div>
          </div>
        </div>

        {autoTrade && (
          <div className={`mt-3 p-2 rounded ${mode === 'paper' ? 'bg-blue-900/50 border border-blue-700' : 'bg-red-900/50 border border-red-700'}`}>
            <p className="text-sm text-gray-200">
              ⚡ Auto-trade ON - Will execute when edge ≥ {minEdge}%
              {mode === 'live' && <span className="text-red-400 font-bold"> (REAL MONEY!)</span>}
            </p>
          </div>
        )}
      </div>

      {/* Execution result */}
      {execResult && (
        <div className={`p-4 rounded-lg ${execResult.success ? 'bg-green-900/50 border border-green-500' : 'bg-red-900/50 border border-red-500'}`}>
          <p className="font-bold text-white">{execResult.success ? '✅ Trade Executed!' : '❌ Execution Failed'}</p>
          {execResult.success && (
            <p className="text-sm text-gray-300 mt-1">{execResult.contracts} contracts | Profit: ${(execResult.profit_cents / 100).toFixed(2)}</p>
          )}
          {execResult.error && <p className="text-sm text-red-300 mt-1">{execResult.error}</p>}
          <button onClick={() => setExecResult(null)} className="text-sm text-blue-400 underline mt-2 hover:text-blue-300">Dismiss</button>
        </div>
      )}

      {/* Opportunities */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-3">
          Live Opportunities: {opportunities.length}
          {status?.last_scan_at && <span className="text-sm font-normal text-gray-400 ml-2">(updated {getTimeAgo(status.last_scan_at)})</span>}
        </h3>

        {opportunities.length === 0 ? (
          <div className="bg-slate-800 rounded-lg p-8 text-center border border-slate-700">
            <p className="text-gray-400">No opportunities above {minEdge}% edge</p>
            <p className="text-sm text-gray-500 mt-2">Scanner checking every {status?.config.scan_interval_seconds}s...</p>
          </div>
        ) : (
          <div className="space-y-4">
            {opportunities.map((opp, idx) => (
              <div key={opp.id} className={`bg-slate-800 rounded-lg p-4 border-2 ${idx === 0 ? 'border-green-500' : 'border-slate-700'}`}>
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <span className="text-lg font-bold text-white">{idx === 0 && '🏆 '}Range: {opp.range_description}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-2xl font-bold text-green-400">{opp.edge_percent.toFixed(1)}%</span>
                    <p className="text-sm text-gray-400">{opp.edge_cents}¢ per set</p>
                  </div>
                </div>

                <div className="bg-slate-700/50 rounded p-3 mb-3 text-sm font-mono">
                  {opp.legs.map((leg, i) => (
                    <div key={i} className="flex justify-between text-gray-300">
                      <span>{leg.side.toUpperCase()} {leg.market_type === 'range' ? 'Range' : `≥$${leg.strike?.toLocaleString()}`}</span>
                      <span className="text-yellow-400">{leg.price_cents}¢</span>
                    </div>
                  ))}
                  <div className="border-t border-slate-600 mt-2 pt-2 flex justify-between font-bold text-white">
                    <span>Total → Payout</span>
                    <span>{opp.total_cost_cents}¢ → 100¢</span>
                  </div>
                </div>

                <button
                  onClick={() => executeOpportunity(opp.id)}
                  disabled={executing === opp.id || autoTrade}
                  className={`w-full py-3 rounded font-bold transition-colors ${
                    autoTrade ? 'bg-gray-600 cursor-not-allowed text-gray-400' : mode === 'paper' ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-red-600 hover:bg-red-700 text-white'
                  } disabled:opacity-50`}
                >
                  {executing === opp.id ? '⏳ Executing...' : autoTrade ? '(Auto-trade enabled)' : `Execute (${mode === 'paper' ? 'Paper' : 'LIVE'})`}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Stats footer */}
      <div className="text-sm text-gray-500 text-center">
        Auto-executions: {status?.auto_executions || 0} | Scans: {status?.total_scans || 0}
        {status?.last_error && <span className="text-red-400 ml-2">| Error: {status.last_error}</span>}
      </div>
    </div>
  );
}

export default BTCArbitrageTab;
