import { useEffect } from 'react';
import { useTradingStore } from '../../stores/tradingStore';
import { api } from '../../services/api';
import { formatCurrency } from '../../utils/format';

export function PositionList() {
  const mode = useTradingStore((s) => s.mode);
  const positions = useTradingStore((s) => s.positions);
  const setPositions = useTradingStore((s) => s.setPositions);

  useEffect(() => {
    const fetch = async () => {
      const res = await api.getPositions();
      setPositions(res.positions);
    };
    fetch();
    const interval = setInterval(fetch, 30000);
    return () => clearInterval(interval);
  }, [mode]);

  if (positions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="font-semibold mb-4">Open Positions</h3>
        <p className="text-gray-400 text-center py-4">No open positions</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="font-semibold mb-4">Open Positions ({positions.length})</h3>
      <div className="space-y-2">
        {positions.map((pos) => (
          <div key={pos.id} className="flex justify-between p-3 bg-gray-700 rounded">
            <div>
              <div className="font-medium">{pos.ticker}</div>
              <div className="text-sm text-gray-400">
                {pos.contracts} contracts @ {(pos.avg_price * 100).toFixed(0)}c
              </div>
            </div>
            <div className="text-right">
              <div>{formatCurrency(pos.total_cost)}</div>
              <div className="text-sm text-gray-400">+ {formatCurrency(pos.total_fees)} fees</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
