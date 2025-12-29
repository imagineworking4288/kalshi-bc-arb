import { useEffect } from 'react';
import { TrendingUp, Clock, DollarSign, Target } from 'lucide-react';
import { useAnalyticsStore } from '../../stores/analyticsStore';
import { api } from '../../services/api';
import { LoadingSpinner } from '../common/LoadingSpinner';

export function AnalyticsDashboard() {
  const {
    period,
    summary,
    byAsset,
    byDate,
    isLoading,
    error,
    setPeriod,
    setSummary,
    setByAsset,
    setByDate,
    setLoading,
    setError,
  } = useAnalyticsStore();

  useEffect(() => {
    loadAnalytics();
  }, [period]);

  const loadAnalytics = async () => {
    setLoading(true);
    setError(null);

    try {
      const [summaryData, assetData, dateData] = await Promise.all([
        api.getAnalyticsSummary(period),
        api.getAnalyticsByAsset(),
        api.getAnalyticsByDate(),
      ]);

      setSummary(summaryData);
      setByAsset(assetData.byAsset);
      setByDate(dateData.byDate);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  if (isLoading && !summary) {
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
    <div className="space-y-6">
      {/* Period selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Analytics</h2>
        <div className="flex bg-gray-700 rounded-lg p-1">
          {(['today', 'week', 'month', 'all'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                period === p
                  ? 'bg-emerald-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-emerald-900/50 rounded-lg">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              </div>
              <span className="text-sm text-gray-400">Opportunities</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {summary.totalOpportunities}
            </p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-blue-900/50 rounded-lg">
                <Target className="w-5 h-5 text-blue-400" />
              </div>
              <span className="text-sm text-gray-400">Avg Profit</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {summary.avgProfitPct.toFixed(2)}%
            </p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-yellow-900/50 rounded-lg">
                <Clock className="w-5 h-5 text-yellow-400" />
              </div>
              <span className="text-sm text-gray-400">Avg Duration</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {formatDuration(summary.avgDurationSeconds)}
            </p>
          </div>

          <div className="bg-gray-800 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-purple-900/50 rounded-lg">
                <DollarSign className="w-5 h-5 text-purple-400" />
              </div>
              <span className="text-sm text-gray-400">Traded</span>
            </div>
            <p className="text-2xl font-bold text-white">{summary.tradedCount}</p>
          </div>
        </div>
      )}

      {/* By asset breakdown */}
      {byAsset.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-4">
            By Asset
          </h3>
          <div className="space-y-3">
            {byAsset.map((item) => (
              <div
                key={item.asset}
                className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
              >
                <div>
                  <p className="font-medium text-white">{item.asset}</p>
                  <p className="text-xs text-gray-400">
                    {item.count} opportunities
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-emerald-400 font-medium">
                    {item.avgProfitPct.toFixed(2)}%
                  </p>
                  <p className="text-xs text-gray-400">avg profit</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity by date */}
      {byDate.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-4">
            Recent Activity
          </h3>
          <div className="space-y-2">
            {byDate.slice(0, 7).map((item) => (
              <div
                key={item.date}
                className="flex items-center justify-between py-2 border-b border-gray-700 last:border-0"
              >
                <span className="text-gray-300">{item.date}</span>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-400">
                    {item.count} opps
                  </span>
                  <span className="text-sm text-emerald-400">
                    {item.avgProfitPct.toFixed(2)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Export button */}
      <div className="flex justify-end">
        <a
          href={api.getExportUrl()}
          download
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg text-sm transition-colors"
        >
          Export CSV
        </a>
      </div>
    </div>
  );
}
