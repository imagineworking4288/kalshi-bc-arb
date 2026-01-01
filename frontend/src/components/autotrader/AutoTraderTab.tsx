import { useEffect, useState } from 'react';

interface AutoTraderConfig {
  enabled: number;
  mode: string;
  is_running: boolean;
  min_edge: number;
  max_position_size: number;
  max_daily_loss_cents: number;
  max_open_positions: number;
  allowed_series: string[];
}

interface Signal {
  id: number;
  ticker: string;
  signal_type: string;
  edge_percent: number;
  model_prob: number;
  market_price: number;
  recommended_size: number;
  source: string;
  status: string;
  created_at: string;
  notes: string;
}

export function AutoTraderTab() {
  const [config, setConfig] = useState<AutoTraderConfig | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [scanResults, setScanResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statusRes, signalsRes] = await Promise.all([
        fetch('/api/auto-trader/status').then(r => r.json()),
        fetch('/api/auto-trader/signals?limit=20').then(r => r.json())
      ]);
      setConfig(statusRes);
      setSignals(signalsRes.signals || []);
    } catch (err) {
      console.error('Failed to load auto-trader data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    try {
      await fetch('/api/auto-trader/start', { method: 'POST' });
      setMessage({ type: 'success', text: 'Auto-trader started' });
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    }
  };

  const handleStop = async () => {
    try {
      await fetch('/api/auto-trader/stop', { method: 'POST' });
      setMessage({ type: 'success', text: 'Auto-trader stopped' });
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setScanResults([]);
    try {
      const res = await fetch('/api/auto-trader/scan').then(r => r.json());
      setScanResults(res.signals || []);
      setMessage({ type: 'success', text: `Scan complete: ${res.count} signals found` });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setScanning(false);
    }
  };

  const updateConfig = async (field: string, value: any) => {
    try {
      await fetch('/api/auto-trader/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value })
      });
      setMessage({ type: 'success', text: 'Config updated' });
      loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    }
  };

  if (loading) {
    return <div className="p-6">Loading auto-trader...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Auto-Trader & Edge Detection</h2>
      </div>

      {/* Message Banner */}
      {message && (
        <div className={`p-4 rounded ${
          message.type === 'success'
            ? 'bg-green-900/20 border border-green-500 text-green-400'
            : 'bg-red-900/20 border border-red-500 text-red-400'
        }`}>
          {message.text}
          <button onClick={() => setMessage(null)} className="float-right">×</button>
        </div>
      )}

      {/* Status & Controls Card */}
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold">Status</h3>
            <p className={`text-sm mt-1 ${config?.is_running ? 'text-green-400' : 'text-gray-400'}`}>
              <span className={config?.is_running ? 'animate-pulse' : ''}>●</span> {config?.is_running ? 'Running' : 'Stopped'} - {config?.mode}
            </p>
          </div>
          <div className="flex gap-2">
            {!config?.is_running ? (
              <button
                onClick={handleStart}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded font-medium transition-colors"
              >
                ▶ Start Auto-Trader
              </button>
            ) : (
              <button
                onClick={handleStop}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded font-medium transition-colors"
              >
                ■ Stop Auto-Trader
              </button>
            )}
            <button
              onClick={handleScan}
              disabled={scanning}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {scanning ? '⟳ Scanning...' : '🔍 Manual Scan'}
            </button>
          </div>
        </div>

        {/* Configuration */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="text-sm text-gray-400 block mb-1">Trading Mode</label>
            <select
              value={config?.enabled || 0}
              onChange={(e) => updateConfig('enabled', parseInt(e.target.value))}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
            >
              <option value={0}>🔒 Disabled</option>
              <option value={1}>📄 Paper Only (Safe)</option>
              <option value={2}>💰 Live Enabled (REAL MONEY)</option>
            </select>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-1">Min Edge %</label>
            <input
              type="number"
              value={config?.min_edge || 10}
              onChange={(e) => updateConfig('min_edge_percent', parseFloat(e.target.value))}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
              min="1"
              max="50"
              step="0.5"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-1">Max Position Size</label>
            <input
              type="number"
              value={config?.max_position_size || 100}
              onChange={(e) => updateConfig('max_position_size', parseInt(e.target.value))}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
              min="1"
              max="1000"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-1">Max Daily Loss $</label>
            <input
              type="number"
              value={(config?.max_daily_loss_cents || 10000) / 100}
              onChange={(e) => updateConfig('max_daily_loss_cents', parseFloat(e.target.value) * 100)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
              min="10"
              max="10000"
              step="10"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-1">Max Open Positions</label>
            <input
              type="number"
              value={config?.max_open_positions || 10}
              onChange={(e) => updateConfig('max_open_positions', parseInt(e.target.value))}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
              min="1"
              max="100"
            />
          </div>
        </div>
      </div>

      {/* Scan Results */}
      {scanResults.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Latest Scan Results ({scanResults.length} edges found)</h3>
          <div className="space-y-2">
            {scanResults.map((s, i) => (
              <div key={i} className="bg-gray-700 rounded p-4 flex justify-between items-center hover:bg-gray-600 transition-colors">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-blue-400">{s.ticker}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      s.signal_type.includes('yes') ? 'bg-green-600' : 'bg-red-600'
                    }`}>
                      {s.signal_type.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400 mt-1">{s.notes}</div>
                </div>
                <div className="text-right">
                  <div className="text-green-400 font-bold text-lg">{s.edge_percent.toFixed(1)}% edge</div>
                  <div className="text-gray-400 text-sm">@ {s.market_price}¢ · Size: {s.recommended_size}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Signal History */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Signal History</h3>
        {signals.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-400 mb-2">No signals generated yet</p>
            <p className="text-sm text-gray-500">Click "Manual Scan" to find edges, or start the auto-trader to scan automatically every minute</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-700">
                <tr className="text-gray-400 text-left">
                  <th className="pb-2">Ticker</th>
                  <th className="pb-2">Signal</th>
                  <th className="pb-2">Edge</th>
                  <th className="pb-2">Price</th>
                  <th className="pb-2">Size</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((s) => (
                  <tr key={s.id} className="border-t border-gray-700 hover:bg-gray-700/50">
                    <td className="py-3 font-mono text-xs text-blue-400">{s.ticker}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        s.signal_type.includes('yes') ? 'bg-green-600' : 'bg-red-600'
                      }`}>
                        {s.signal_type}
                      </span>
                    </td>
                    <td className="py-3 text-green-400 font-medium">{s.edge_percent.toFixed(1)}%</td>
                    <td className="py-3">{s.market_price}¢</td>
                    <td className="py-3">{s.recommended_size}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        s.status === 'executed' ? 'bg-green-600' :
                        s.status === 'pending' ? 'bg-yellow-600' :
                        s.status === 'rejected' ? 'bg-red-600' :
                        'bg-gray-600'
                      }`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="py-3 text-gray-400 text-xs">
                      {new Date(s.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Info Card */}
      <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
        <h4 className="font-semibold text-blue-400 mb-2">How Auto-Trading Works</h4>
        <ul className="text-sm text-gray-300 space-y-1">
          <li>• <strong>Edge Detection:</strong> Compares BTC spot price to Kalshi market strikes to find mispriced markets</li>
          <li>• <strong>Auto-Execution:</strong> When enabled, automatically places trades on detected edges (respects position limits)</li>
          <li>• <strong>Risk Management:</strong> Daily loss limits and position size caps prevent runaway losses</li>
          <li>• <strong>Paper Mode:</strong> Test the system with simulated trades before using real money</li>
          <li>• <strong>Scan Frequency:</strong> Runs every 60 seconds when auto-trader is running</li>
        </ul>
      </div>
    </div>
  );
}
