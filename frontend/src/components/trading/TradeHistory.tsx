import { useEffect, useState } from 'react';
import { useTradingStore } from '../../stores/tradingStore';
import { api } from '../../services/api';
import { formatCurrency } from '../../utils/format';
import type { Trade } from '../../types';

export function TradeHistory() {
  const mode = useTradingStore((s) => s.mode);
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    if (mode === 'paper') {
      api.getPaperTrades().then((res) => setTrades(res.trades));
    }
  }, [mode]);

  if (mode !== 'paper' || trades.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="font-semibold mb-4">Trade History</h3>
      <div className="space-y-2">
        {trades.slice(0, 10).map((trade) => (
          <div key={trade.id} className="flex justify-between p-3 bg-gray-700 rounded">
            <div>
              <div className="font-medium">{trade.asset} Arbitrage</div>
              <div className="text-sm text-gray-400">
                {new Date(trade.executed_at).toLocaleString()}
              </div>
            </div>
            <div className="text-right">
              <div className="text-green-400">+{formatCurrency(trade.expected_profit)}</div>
              <div className="text-sm text-gray-400">{trade.status}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
