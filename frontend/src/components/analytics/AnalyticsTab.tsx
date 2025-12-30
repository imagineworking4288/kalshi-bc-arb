import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { formatCurrency } from '../../utils/format';
import type { PnLSummary } from '../../types';

export function AnalyticsTab() {
  const [summary, setSummary] = useState<PnLSummary | null>(null);

  useEffect(() => {
    api.getPaperSummary().then(setSummary);
  }, []);

  if (!summary) {
    return <div className="text-center py-8 text-gray-400">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">Paper Trading Analytics</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Current Balance</div>
          <div className="text-2xl font-bold">{formatCurrency(summary.current_balance)}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Total P&L</div>
          <div className={`text-2xl font-bold ${summary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {summary.total_pnl >= 0 ? '+' : ''}{formatCurrency(summary.total_pnl)}
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">P&L %</div>
          <div className={`text-2xl font-bold ${summary.total_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {summary.total_pnl_pct >= 0 ? '+' : ''}{summary.total_pnl_pct.toFixed(2)}%
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Total Trades</div>
          <div className="text-2xl font-bold">{summary.total_trades}</div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="font-semibold mb-4">Details</h3>
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-gray-400">Starting Balance</span>
            <span>{formatCurrency(summary.starting_balance)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Realized P&L</span>
            <span>{formatCurrency(summary.realized_pnl)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Open Positions Value</span>
            <span>{formatCurrency(summary.open_positions_value)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
