import { useEffect, useState } from 'react';
import { api } from '../../services/api';

interface PortfolioSummary {
  paper_balance: number;
  live_balance: number;
  paper_positions_count: number;
  live_positions_count: number;
}

interface Position {
  ticker: string;
  side: string;
  contracts: number;
  avg_price: number;
  total_cost: number;
  mode: string;
  created_at: string;
}

interface Order {
  id: string;
  ticker: string;
  side: string;
  action: string;
  count: number;
  price_cents: number;
  mode: string;
  status: string;
  created_at: string;
}

export function PortfolioTab() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedMode, setSelectedMode] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [selectedMode]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, positionsData, ordersData] = await Promise.all([
        api.getPortfolioSummary(),
        api.getPortfolioPositions(),
        api.getPortfolioOrders(selectedMode === 'all' ? undefined : selectedMode)
      ]);

      setSummary(summaryData);
      setPositions(positionsData.positions);
      setOrders(ordersData.orders);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading portfolio...</div>;
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500 rounded-lg p-4">
        <p className="text-red-400">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Paper Balance</div>
          <div className="text-2xl font-bold text-white">
            ${summary?.paper_balance.toFixed(2)}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Live Balance</div>
          <div className="text-2xl font-bold text-white">
            ${summary?.live_balance.toFixed(2)}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Paper Positions</div>
          <div className="text-2xl font-bold text-white">
            {summary?.paper_positions_count || 0}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm text-gray-400">Live Positions</div>
          <div className="text-2xl font-bold text-white">
            {summary?.live_positions_count || 0}
          </div>
        </div>
      </div>

      {/* Positions */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Positions</h2>
        {positions.length === 0 ? (
          <p className="text-gray-400 text-center py-4">No positions yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-gray-700">
                <tr className="text-left text-sm text-gray-400">
                  <th className="pb-2">Ticker</th>
                  <th className="pb-2">Side</th>
                  <th className="pb-2">Contracts</th>
                  <th className="pb-2">Avg Price</th>
                  <th className="pb-2">Total Cost</th>
                  <th className="pb-2">Mode</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, idx) => (
                  <tr key={idx} className="border-b border-gray-700/50">
                    <td className="py-3 font-mono text-sm">{pos.ticker}</td>
                    <td className="py-3">
                      <span className={pos.side === 'yes' ? 'text-green-400' : 'text-red-400'}>
                        {pos.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3">{pos.contracts}</td>
                    <td className="py-3">${pos.avg_price.toFixed(2)}</td>
                    <td className="py-3">${pos.total_cost.toFixed(2)}</td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs ${
                        pos.mode === 'paper'
                          ? 'bg-blue-900/30 text-blue-400'
                          : 'bg-green-900/30 text-green-400'
                      }`}>
                        {pos.mode}
                      </span>
                    </td>
                    <td className="py-3 text-sm text-gray-400">
                      {new Date(pos.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Order History */}
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Order History</h2>

          {/* Mode Filter */}
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedMode('all')}
              className={`px-3 py-1 rounded text-sm ${
                selectedMode === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setSelectedMode('paper')}
              className={`px-3 py-1 rounded text-sm ${
                selectedMode === 'paper'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              Paper
            </button>
            <button
              onClick={() => setSelectedMode('live')}
              className={`px-3 py-1 rounded text-sm ${
                selectedMode === 'live'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              Live
            </button>
          </div>
        </div>

        {orders.length === 0 ? (
          <p className="text-gray-400 text-center py-4">No orders yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-gray-700">
                <tr className="text-left text-sm text-gray-400">
                  <th className="pb-2">Ticker</th>
                  <th className="pb-2">Side</th>
                  <th className="pb-2">Action</th>
                  <th className="pb-2">Count</th>
                  <th className="pb-2">Price</th>
                  <th className="pb-2">Mode</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id} className="border-b border-gray-700/50">
                    <td className="py-3 font-mono text-sm">{order.ticker}</td>
                    <td className="py-3">
                      <span className={order.side === 'yes' ? 'text-green-400' : 'text-red-400'}>
                        {order.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 capitalize">{order.action}</td>
                    <td className="py-3">{order.count}</td>
                    <td className="py-3">${(order.price_cents / 100).toFixed(2)}</td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs ${
                        order.mode === 'paper'
                          ? 'bg-blue-900/30 text-blue-400'
                          : 'bg-green-900/30 text-green-400'
                      }`}>
                        {order.mode}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className={`px-2 py-1 rounded text-xs ${
                        order.status === 'filled'
                          ? 'bg-green-900/30 text-green-400'
                          : order.status === 'failed'
                          ? 'bg-red-900/30 text-red-400'
                          : 'bg-yellow-900/30 text-yellow-400'
                      }`}>
                        {order.status}
                      </span>
                    </td>
                    <td className="py-3 text-sm text-gray-400">
                      {new Date(order.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
