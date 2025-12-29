import { useState, useEffect } from 'react';
import { Clock, TrendingUp, Check, X } from 'lucide-react';
import { api } from '../../services/api';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { Badge } from '../common/Badge';
import type { HistoricalOpportunity } from '../../types';

export function HistoryView() {
  const [opportunities, setOpportunities] = useState<HistoricalOpportunity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'traded'>('all');

  useEffect(() => {
    loadHistory();
  }, [filter]);

  const loadHistory = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await api.getOpportunityHistory({
        tradedOnly: filter === 'traded',
        limit: 100,
      });
      setOpportunities(data.opportunities);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return 'Active';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (isLoading && opportunities.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 text-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">History</h2>
        <div className="flex bg-gray-700 rounded-lg p-1">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filter === 'all'
                ? 'bg-emerald-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('traded')}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filter === 'traded'
                ? 'bg-emerald-600 text-white'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            Traded
          </button>
        </div>
      </div>

      {/* List */}
      {opportunities.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-400">No history found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {opportunities.map((opp) => (
            <div
              key={opp.id}
              className="bg-gray-800 rounded-lg p-4 border border-gray-700"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge size="sm">{opp.asset}</Badge>
                    <span className="text-sm text-gray-400">
                      {formatCurrency(opp.thresholdStrike)}
                    </span>
                    {opp.wasTraded && (
                      <Badge variant="success" size="sm">
                        <Check className="w-3 h-3 mr-1" />
                        Traded
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">
                    {formatDate(opp.detectedAt)}
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-emerald-400 font-medium">
                    {opp.netProfitPct.toFixed(2)}%
                  </p>
                  <p className="text-xs text-gray-500">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {formatDuration(opp.durationSeconds)}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Threshold</p>
                  <p className="text-white">
                    {(opp.thresholdYesPrice * 100).toFixed(0)}c
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Implied</p>
                  <p className="text-white">
                    {(opp.impliedPrice * 100).toFixed(0)}c
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Divergence</p>
                  <p
                    className={
                      opp.divergence > 0 ? 'text-red-400' : 'text-emerald-400'
                    }
                  >
                    {opp.divergence > 0 ? '+' : ''}
                    {(opp.divergence * 100).toFixed(1)}c
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Liquidity</p>
                  <p className="text-white">{formatCurrency(opp.maxLiquidityUsd)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
