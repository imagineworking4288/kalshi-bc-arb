import { useState, useEffect, useRef } from 'react';
import { StatsBar } from './shared/StatsBar';
import { ConfigPanel } from './shared/ConfigPanel';
import { OpportunityTable } from './shared/OpportunityTable';

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
  all_calculations: Calculation[];
  near_misses: Calculation[];
  profitable: Calculation[];
  stats: Stats;
  activity_log: LogEntry[];
}

type TabType = 'near_misses' | 'calculations' | 'markets' | 'log' | 'opportunities';
type ViewMode = 'overview' | 'scanner';

interface CryptoAsset {
  id: string;
  name: string;
  code: string;
  icon: string;
  series: string;
  thresholdSeries: string;
  enabled: boolean;
  color: string;
  borderColor: string;
}

export function CryptoArbitrageSection() {
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [selectedAsset, setSelectedAsset] = useState<string>('BTC');

  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const [execResult, setExecResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<TabType>('near_misses');

  const [minEdge, setMinEdge] = useState(3.0);
  const [budgetDollars, setBudgetDollars] = useState(100);
  const [autoTrade, setAutoTrade] = useState(false);
  const [mode, setMode] = useState<'paper' | 'live'>('paper');

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cryptoAssets: CryptoAsset[] = [
    {
      id: 'BTC',
      name: 'Bitcoin',
      code: 'BTC',
      icon: '₿',
      series: 'KXBTC',
      thresholdSeries: 'KXBTCD',
      enabled: true,
      color: 'from-orange-900/30 to-yellow-900/30',
      borderColor: 'border-orange-500/50'
    },
    {
      id: 'ETH',
      name: 'Ethereum',
      code: 'ETH',
      icon: 'Ξ',
      series: 'KXETH',
      thresholdSeries: 'KXETHD',
      enabled: false,
      color: 'from-blue-900/30 to-purple-900/30',
      borderColor: 'border-blue-500/50'
    },
    {
      id: 'SOL',
      name: 'Solana',
      code: 'SOL',
      icon: '◎',
      series: 'KXSOL',
      thresholdSeries: 'KXSOLD',
      enabled: false,
      color: 'from-purple-900/30 to-pink-900/30',
      borderColor: 'border-purple-500/50'
    },
    {
      id: 'XRP',
      name: 'XRP',
      code: 'XRP',
      icon: '✕',
      series: 'KXXRP',
      thresholdSeries: 'KXXRPD',
      enabled: false,
      color: 'from-gray-900/30 to-slate-900/30',
      borderColor: 'border-gray-500/50'
    }
  ];

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
    pollRef.current = setInterval(fetchStatus, 2000);

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

  const copyTickersToClipboard = (calc: Calculation) => {
    const tickers = [
      `Range: ${calc.range_ticker}`,
      `Lower: ${calc.lower_thresh_ticker || 'N/A'}`,
      `Upper: ${calc.upper_thresh_ticker || 'N/A'}`
    ].join('\n');
    navigator.clipboard.writeText(tickers);
    alert('Tickers copied to clipboard!');
  };

  const handleViewScanner = (assetId: string) => {
    setSelectedAsset(assetId);
    setViewMode('scanner');
  };

  const handleBackToOverview = () => {
    setViewMode('overview');
  };

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="text-gray-400">Loading arbitrage engine...</div>
      </div>
    );
  }

  // Overview Mode - Card Grid
  if (viewMode === 'overview') {
    return (
      <div className="space-y-4">
        {/* Explanation Banner */}
        <div className="bg-gradient-to-r from-orange-900/20 to-yellow-900/20 border border-orange-500/30 rounded-lg p-4">
          <h3 className="text-lg font-bold text-white mb-2">₿ Crypto Range vs Threshold Arbitrage</h3>
          <p className="text-sm text-gray-300 mb-2">
            Buy Range YES + Lower Threshold NO + Upper Threshold YES for guaranteed $1 payout when total cost is less than 100¢.
          </p>
          <div className="text-xs text-gray-400">
            <strong>Strategy:</strong> Each crypto has range markets (e.g., "BTC $90k-$95k") and threshold markets (e.g., "BTC ≥$92k").
            If you can buy all three positions for less than $1 total, you're guaranteed a $1 payout regardless of the final price.
          </div>
        </div>

        {/* Crypto Cards Grid */}
        <div className="grid grid-cols-2 gap-4">
          {cryptoAssets.map((asset) => {
            const isLive = asset.enabled && status;
            const stats = asset.enabled && status ? status.stats : null;
            const rangeCount = asset.enabled && status ? status.market_data.range_markets.length : 0;
            const thresholdCount = asset.enabled && status ? status.market_data.threshold_markets.length : 0;

            return (
              <div
                key={asset.id}
                className={`bg-gradient-to-br ${asset.color} border ${asset.borderColor} rounded-lg p-4 relative overflow-hidden`}
              >
                {/* Status Badge */}
                <div className="absolute top-2 right-2">
                  {isLive ? (
                    <span className="px-2 py-1 bg-green-600/80 text-green-100 text-xs font-bold rounded flex items-center gap-1">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-300 animate-pulse"></span>
                      LIVE
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-yellow-600/80 text-yellow-100 text-xs font-bold rounded">
                      COMING SOON
                    </span>
                  )}
                </div>

                {/* Crypto Icon */}
                <div className="text-4xl mb-2 font-bold">{asset.icon}</div>

                {/* Crypto Name */}
                <h4 className="text-lg font-bold text-white mb-1">{asset.name}</h4>
                <p className="text-xs text-gray-400 mb-1">Market Code: {asset.code}</p>
                <p className="text-xs text-gray-500 mb-3">Series: {asset.series} / {asset.thresholdSeries}</p>

                {/* Stats */}
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Ranges:</span>
                    <span className={isLive ? 'text-blue-400 font-medium' : 'text-gray-500'}>{isLive ? rangeCount : '-'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Thresholds:</span>
                    <span className={isLive ? 'text-purple-400 font-medium' : 'text-gray-500'}>{isLive ? thresholdCount : '-'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Best Cost:</span>
                    <span className={isLive && stats ? getCostColor(stats.best_cost) + ' font-medium' : 'text-gray-500'}>
                      {isLive && stats && stats.best_cost !== null ? `${stats.best_cost}¢` : '-'}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Near Misses:</span>
                    <span className={isLive && stats ? 'text-orange-400 font-medium' : 'text-gray-500'}>
                      {isLive && stats ? stats.near_misses : 0}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Opportunities:</span>
                    <span className={isLive && status && status.opportunities.length > 0 ? 'text-green-400 font-bold' : 'text-gray-500'}>
                      {isLive && status ? status.opportunities.length : 0}
                    </span>
                  </div>
                </div>

                {/* Action Button */}
                <button
                  onClick={() => asset.enabled && handleViewScanner(asset.id)}
                  disabled={!asset.enabled}
                  className={`w-full mt-3 py-2 rounded text-sm font-medium transition-colors ${
                    asset.enabled
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-slate-700/50 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  {asset.enabled ? 'View Scanner' : 'Scanner Disabled'}
                </button>
              </div>
            );
          })}
        </div>

        {/* Info Section */}
        <div className="bg-slate-800 rounded-lg p-4">
          <h4 className="text-sm font-bold text-white mb-2">How Crypto Arbitrage Works</h4>
          <div className="text-xs text-gray-400 space-y-2">
            <p>
              <strong className="text-white">1. Range Markets:</strong> Markets for price ranges like "Will BTC be between $90,000-$95,000?"
              You buy YES on the range market.
            </p>
            <p>
              <strong className="text-white">2. Threshold Markets:</strong> Markets for price thresholds like "Will BTC be ≥$90,000?" and "Will BTC be ≥$95,000?"
              You buy NO on the lower threshold and YES on the upper threshold.
            </p>
            <p>
              <strong className="text-white">3. Guaranteed Profit:</strong> If the range is $90k-$95k:
              • If BTC &lt; $90k: Lower threshold NO pays $1
              • If BTC $90k-$95k: Range YES pays $1
              • If BTC ≥ $95k: Upper threshold YES pays $1
            </p>
            <p>
              <strong className="text-white">4. Example:</strong> Range YES costs 35¢ + Lower NO costs 32¢ + Upper YES costs 31¢ = 98¢ total.
              You spend 98¢ and receive $1.00 payout for a 2¢ guaranteed profit.
            </p>
            <p className="text-yellow-400 mt-3">
              💡 The scanner automatically finds these opportunities when the total cost is less than 100¢.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Scanner Mode - Detailed View
  if (!status) {
    return (
      <div className="p-6 text-center">
        <div className="text-red-400 mb-2">Could not connect to Arbitrage Engine</div>
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
  const allCalculations = status?.all_calculations || [];
  const nearMisses = status?.near_misses || [];
  const profitableCalcs = status?.profitable || [];
  const rangeMarkets = status?.market_data?.range_markets || [];
  const thresholdMarkets = status?.market_data?.threshold_markets || [];
  const activityLog = status?.activity_log || [];
  const stats = status?.stats || {};

  // Stats for StatsBar
  const statsData = [
    { value: status?.total_scans || 0, label: 'Scans', color: 'text-yellow-400' },
    { value: stats.ranges_checked || 0, label: 'Ranges', color: 'text-blue-400' },
    { value: stats.thresholds_found || 0, label: 'Thresholds', color: 'text-purple-400' },
    { value: stats.best_cost !== null ? `${stats.best_cost}¢` : '-', label: 'Best Cost', color: getCostColor(stats.best_cost) },
    { value: stats.near_misses || 0, label: 'Near Miss', color: 'text-orange-400' },
    { value: opportunities.length, label: 'Opps', color: 'text-green-400' }
  ];

  // Table columns for near-misses
  const nearMissColumns = [
    { key: 'range', label: 'Price Range', align: 'left' as const },
    { key: 'range_yes', label: 'Range YES', align: 'right' as const },
    { key: 'lower_no', label: 'Lower Thresh NO', align: 'right' as const },
    { key: 'upper_yes', label: 'Upper Thresh YES', align: 'right' as const },
    { key: 'total', label: 'Total Cost', align: 'right' as const, bold: true },
    { key: 'edge', label: 'Edge', align: 'right' as const }
  ];

  const renderNearMissCell = (calc: Calculation, col: any) => {
    switch (col.key) {
      case 'range':
        return (
          <>
            <div className="text-white font-medium">{calc.range_description}</div>
            <span className="inline-block px-2 py-0.5 bg-blue-600/80 text-white text-xs rounded-full font-medium mt-1">
              {calc.event_date}
            </span>
          </>
        );
      case 'range_yes':
        return <span className="font-mono text-blue-400">{calc.range_yes_ask !== null ? `${calc.range_yes_ask}¢` : '-'}</span>;
      case 'lower_no':
        return <span className="font-mono text-purple-400">{calc.lower_thresh_no_cost !== null ? `${calc.lower_thresh_no_cost}¢` : '-'}</span>;
      case 'upper_yes':
        return <span className="font-mono text-cyan-400">{calc.upper_thresh_yes_ask !== null ? `${calc.upper_thresh_yes_ask}¢` : '-'}</span>;
      case 'total':
        return <span className={`font-mono font-bold ${getCostColor(calc.total_cost_cents)}`}>{calc.total_cost_cents !== null ? `${calc.total_cost_cents}¢` : '-'}</span>;
      case 'edge':
        return (
          <span className={`font-mono ${calc.edge_cents !== null && calc.edge_cents > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {calc.edge_cents !== null ? `${calc.edge_cents > 0 ? '+' : ''}${calc.edge_cents}¢` : '-'}
          </span>
        );
      default:
        return null;
    }
  };

  const getNearMissRowClassName = (calc: Calculation) => {
    if (calc.total_cost_cents !== null && calc.total_cost_cents < 100) {
      return 'bg-green-900/40 hover:bg-green-900/50';
    }
    if (calc.total_cost_cents !== null && calc.total_cost_cents <= 101) {
      return 'bg-yellow-900/40 hover:bg-yellow-900/50';
    }
    return '';
  };

  const currentAsset = cryptoAssets.find(a => a.id === selectedAsset);

  return (
    <div className="space-y-4">
      {/* Back Button & Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleBackToOverview}
          className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1"
        >
          ← Back to Overview
        </button>
        <div className="flex items-center gap-2">
          <span className="text-2xl">{currentAsset?.icon}</span>
          <h3 className="text-lg font-bold text-white">{currentAsset?.name} Scanner</h3>
          <div className={`px-3 py-1 rounded font-bold text-sm ${mode === 'paper' ? 'bg-blue-600' : 'bg-red-600'} text-white`}>
            {mode === 'paper' ? 'PAPER' : 'LIVE'}
          </div>
          {status?.is_running ? (
            <span className="text-green-400 text-sm">SCANNING (every {status?.config?.scan_interval_seconds ?? 2}s)</span>
          ) : (
            <span className="text-red-400 text-sm">STOPPED</span>
          )}
          {status?.last_scan_at && (
            <span className="text-gray-400 text-sm">Last: {getTimeAgo(status.last_scan_at)} ({status.last_scan_duration_ms}ms)</span>
          )}
        </div>
      </div>

      {/* Stats Bar */}
      <StatsBar stats={statsData} />

      {/* Config Panel */}
      <ConfigPanel
        minEdge={minEdge}
        budgetDollars={budgetDollars}
        mode={mode}
        autoTrade={autoTrade}
        onMinEdgeChange={handleMinEdgeChange}
        onBudgetChange={handleBudgetChange}
        onModeChange={handleModeChange}
        onAutoTradeToggle={handleAutoTradeToggle}
        extraInfo={`Events: ${(stats.event_dates || []).join(', ') || 'None'}`}
      />

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
          { key: 'near_misses', label: `Near Misses (${nearMisses.length})`, highlight: nearMisses.length > 0 },
          { key: 'opportunities', label: `Profitable (${profitableCalcs.length})`, highlight: profitableCalcs.length > 0 },
          { key: 'calculations', label: `All (${allCalculations.length})` },
          { key: 'markets', label: `Markets (${rangeMarkets.length}/${thresholdMarkets.length})` },
          { key: 'log', label: `Log (${activityLog.length})` }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as TabType)}
            className={`px-4 py-2 text-sm font-medium ${
              activeTab === tab.key
                ? 'text-blue-400 border-b-2 border-blue-400'
                : tab.highlight
                ? 'text-yellow-400 hover:text-yellow-300'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-slate-800 rounded-lg p-4 max-h-96 overflow-y-auto">
        {activeTab === 'near_misses' && (
          <div>
            {/* Best Opportunity Banner */}
            {profitableCalcs.length > 0 && profitableCalcs[0].total_cost_cents !== null && profitableCalcs[0].total_cost_cents < 100 && (
              <div className="mb-4 p-4 rounded-lg bg-gradient-to-r from-green-900/50 to-emerald-900/50 border-2 border-green-500">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="text-green-400 text-xs font-bold mb-1">🏆 BEST OPPORTUNITY</div>
                    <div className="text-white font-bold text-lg">{profitableCalcs[0].range_description}</div>
                    <span className="inline-block px-2 py-0.5 bg-blue-600 text-white text-xs rounded-full font-medium mt-1">
                      {profitableCalcs[0].event_date}
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-green-400">{profitableCalcs[0].total_cost_cents}¢</div>
                    <div className="text-sm text-green-300">
                      Profit: {profitableCalcs[0].edge_cents !== null ? `${profitableCalcs[0].edge_cents}¢` : '-'}
                    </div>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-300 font-mono grid grid-cols-3 gap-2">
                  <div>Range YES: <span className="text-blue-400">{profitableCalcs[0].range_yes_ask ?? '-'}¢</span></div>
                  <div>Lower NO: <span className="text-purple-400">{profitableCalcs[0].lower_thresh_no_cost ?? '-'}¢</span></div>
                  <div>Upper YES: <span className="text-cyan-400">{profitableCalcs[0].upper_thresh_yes_ask ?? '-'}¢</span></div>
                </div>
              </div>
            )}

            <OpportunityTable
              columns={nearMissColumns}
              data={nearMisses}
              onRowClick={copyTickersToClipboard}
              getRowClassName={getNearMissRowClassName}
              renderCell={renderNearMissCell}
              emptyMessage={
                <div>
                  No near-misses (cost 100-105¢) found
                  <div className="text-xs mt-2">Best cost: {stats.best_cost !== null ? `${stats.best_cost}¢` : '-'}</div>
                </div>
              }
              footerMessage={`Showing ${nearMisses.length} near-misses (100-105¢) sorted by cost | Green = profitable (<100¢) | Yellow = very close (≤101¢) | Click row to copy tickers`}
            />
          </div>
        )}

        {activeTab === 'calculations' && (
          <OpportunityTable
            columns={nearMissColumns}
            data={allCalculations}
            onRowClick={copyTickersToClipboard}
            getRowClassName={(calc) => {
              if (calc.total_cost_cents !== null && calc.total_cost_cents < 100) return 'bg-green-900/40 hover:bg-green-900/50';
              if (calc.total_cost_cents !== null && calc.total_cost_cents <= 101) return 'bg-yellow-900/40 hover:bg-yellow-900/50';
              if (calc.total_cost_cents !== null && calc.total_cost_cents <= 105) return 'bg-yellow-900/20 hover:bg-yellow-900/30';
              return '';
            }}
            renderCell={renderNearMissCell}
            emptyMessage="No calculations yet - waiting for scan"
            footerMessage={`Sorted by total cost (lowest first) | Green = profitable (<100¢) | Yellow = near-miss | Click row to copy tickers`}
          />
        )}

        {activeTab === 'markets' && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-bold text-blue-400 mb-2">{currentAsset?.series} Range Markets ({rangeMarkets.length})</h4>
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
            <div>
              <h4 className="text-sm font-bold text-purple-400 mb-2">{currentAsset?.thresholdSeries} Threshold Markets ({thresholdMarkets.length})</h4>
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

export default CryptoArbitrageSection;
