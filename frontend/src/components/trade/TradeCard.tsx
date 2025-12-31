import { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { useTradingStore } from '../../stores/tradingStore';

interface Market {
  ticker: string;
  title: string;
  subtitle: string;
  status: string;
  yes_ask: number;
  no_ask: number;
  yes_bid: number;
  no_bid: number;
  volume: number;
}

interface TradeCardProps {
  ticker: string;
}

export function TradeCard({ ticker }: TradeCardProps) {
  const [market, setMarket] = useState<Market | null>(null);
  const [loading, setLoading] = useState(true);
  const [quantity, setQuantity] = useState(1);
  const [paperMode, setPaperMode] = useState(true);
  const [liveMode, setLiveMode] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const balance = useTradingStore((s) => s.balance);

  useEffect(() => {
    const loadMarket = async () => {
      try {
        const data = await api.getMarketDetails(ticker);
        setMarket(data);
      } catch (err) {
        console.error('Failed to load market:', err);
      } finally {
        setLoading(false);
      }
    };
    loadMarket();
  }, [ticker]);

  const executeTrade = async (side: 'yes' | 'no', action: 'buy' | 'sell') => {
    if (!market) return;

    const modes: ('paper' | 'live')[] = [];
    if (paperMode) modes.push('paper');
    if (liveMode) modes.push('live');

    if (modes.length === 0) {
      setLastResult('Error: Select at least one mode (Paper or Live)');
      return;
    }

    const priceCents = side === 'yes' ? market.yes_ask : market.no_ask;

    setExecuting(true);
    setLastResult(null);

    try {
      const result = await api.placeTrade({
        ticker: market.ticker,
        side,
        action,
        count: quantity,
        price_cents: priceCents,
        modes
      });

      if (result.success) {
        setLastResult(`SUCCESS: ${result.message}`);
        // Refresh balance
        const newBalance = await api.getBalance();
        useTradingStore.getState().setBalance(newBalance);
      } else {
        const errors = result.results
          .filter((r) => r.status === 'failed')
          .map((r) => `${r.mode}: ${r.error}`)
          .join(', ');
        setLastResult(`FAILED: ${errors || result.message}`);
      }
    } catch (err) {
      setLastResult(`ERROR: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="text-gray-400">Loading market...</div>
      </div>
    );
  }

  if (!market) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="text-red-400">Failed to load market: {ticker}</div>
      </div>
    );
  }

  const yesCost = (quantity * (market.yes_ask / 100)).toFixed(2);
  const noCost = (quantity * (market.no_ask / 100)).toFixed(2);

  return (
    <div className="bg-gray-800 rounded-lg p-6 space-y-4">
      {/* Header */}
      <div className="border-b border-gray-700 pb-4">
        <div className="text-xs text-gray-500 mb-1">{market.ticker}</div>
        <h3 className="text-lg font-bold">{market.title}</h3>
        {market.subtitle && <div className="text-sm text-gray-400 mt-1">{market.subtitle}</div>}
        <div className="flex items-center gap-3 mt-2 text-xs">
          <span className={`px-2 py-0.5 rounded ${market.status === 'active' ? 'bg-green-900 text-green-200' : 'bg-gray-700 text-gray-400'}`}>
            {market.status}
          </span>
          <span className="text-gray-500">Vol: {market.volume}</span>
        </div>
      </div>

      {/* Prices */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-900 rounded p-3">
          <div className="text-xs text-gray-500 mb-1">YES</div>
          <div className="text-2xl font-bold text-green-400">{market.yes_ask}¢</div>
          <div className="text-xs text-gray-500 mt-1">Bid: {market.yes_bid}¢</div>
        </div>
        <div className="bg-gray-900 rounded p-3">
          <div className="text-xs text-gray-500 mb-1">NO</div>
          <div className="text-2xl font-bold text-red-400">{market.no_ask}¢</div>
          <div className="text-xs text-gray-500 mt-1">Bid: {market.no_bid}¢</div>
        </div>
      </div>

      {/* Quantity Input */}
      <div>
        <label className="block text-sm text-gray-400 mb-2">Quantity (contracts)</label>
        <input
          type="number"
          min="1"
          value={quantity}
          onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
          className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-white"
        />
      </div>

      {/* Mode Selection */}
      <div className="space-y-2">
        <div className="text-sm text-gray-400 mb-2">Execute in:</div>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={paperMode}
            onChange={(e) => setPaperMode(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm">
            Paper Mode <span className="text-gray-500">(Balance: ${balance?.available_balance?.toFixed(2) || '0.00'})</span>
          </span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={liveMode}
            onChange={(e) => setLiveMode(e.target.checked)}
            className="rounded"
          />
          <span className="text-sm text-yellow-400">
            Live Mode (REAL MONEY)
          </span>
        </label>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => executeTrade('yes', 'buy')}
          disabled={executing || market.status !== 'active'}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-3 rounded"
        >
          {executing ? 'Executing...' : `Buy YES ($${yesCost})`}
        </button>
        <button
          onClick={() => executeTrade('no', 'buy')}
          disabled={executing || market.status !== 'active'}
          className="bg-red-600 hover:bg-red-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-3 rounded"
        >
          {executing ? 'Executing...' : `Buy NO ($${noCost})`}
        </button>
      </div>

      {/* Result Message */}
      {lastResult && (
        <div
          className={`p-3 rounded text-sm ${
            lastResult.startsWith('SUCCESS')
              ? 'bg-green-900/50 text-green-200 border border-green-700'
              : 'bg-red-900/50 text-red-200 border border-red-700'
          }`}
        >
          {lastResult}
        </div>
      )}
    </div>
  );
}
