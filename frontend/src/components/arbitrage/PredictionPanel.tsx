/**
 * Weather Prediction Panel Component
 *
 * Addresses Issues #14-#17:
 * - #14: Error boundary wrapper
 * - #15: Loading skeleton states
 * - #16: Stale data indicator
 * - #17: Data source badge
 */

import React, { useState, useCallback, Component, ErrorInfo, ReactNode } from 'react';
import { usePredictions, useSupportedCities, BracketPrediction } from '../../hooks/usePredictions';

// ============ Error Boundary (Issue #14) ============

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class PredictionErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PredictionPanel error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="p-4 bg-red-900/30 border border-red-700 rounded-lg">
          <h3 className="text-red-400 font-semibold mb-2">Something went wrong</h3>
          <p className="text-red-300 text-sm">{this.state.error?.message || 'Unknown error'}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-3 px-3 py-1 bg-red-700 hover:bg-red-600 text-white rounded text-sm"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// ============ Loading Skeleton (Issue #15) ============

const LoadingSkeleton: React.FC = () => (
  <div className="animate-pulse space-y-4">
    <div className="h-8 bg-gray-700 rounded w-1/3"></div>
    <div className="h-24 bg-gray-700 rounded"></div>
    <div className="grid grid-cols-3 gap-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-32 bg-gray-700 rounded"></div>
      ))}
    </div>
    <div className="space-y-2">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="h-16 bg-gray-700 rounded"></div>
      ))}
    </div>
  </div>
);

// ============ Sub-components ============

interface DataSourceBadgeProps {
  source: string;
  cached: boolean;
}

const DataSourceBadge: React.FC<DataSourceBadgeProps> = ({ source, cached }) => (
  <div className="flex gap-2">
    <span
      className={`px-2 py-1 text-xs rounded font-medium ${
        source === 'nws'
          ? 'bg-blue-900/50 text-blue-300'
          : 'bg-orange-900/50 text-orange-300'
      }`}
    >
      {source === 'nws' ? 'NWS' : 'Open-Meteo'}
    </span>
    {cached && (
      <span className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-400">
        Cached
      </span>
    )}
  </div>
);

interface StaleWarningProps {
  cacheAge: number;
}

const StaleWarning: React.FC<StaleWarningProps> = ({ cacheAge }) => {
  const minutes = Math.floor(cacheAge / 60);

  if (minutes < 30) return null;

  return (
    <div className="p-3 bg-yellow-900/30 border border-yellow-700 rounded-lg mb-4">
      <div className="flex items-center gap-2 text-yellow-400">
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <span className="font-medium">Stale Data Warning</span>
      </div>
      <p className="text-yellow-300 text-sm mt-1">
        Data is {minutes} minutes old. Consider refreshing before trading.
      </p>
    </div>
  );
};

interface ForecastHeaderProps {
  city: string;
  forecastHigh: number;
  forecastLow: number;
  weatherPattern: string;
  shortForecast: string;
  source: string;
  cached: boolean;
  cacheAge: number;
  onRefresh: () => void;
  refreshing: boolean;
}

const ForecastHeader: React.FC<ForecastHeaderProps> = ({
  city,
  forecastHigh,
  forecastLow,
  weatherPattern,
  shortForecast,
  source,
  cached,
  cacheAge,
  onRefresh,
  refreshing,
}) => (
  <div className="p-4 bg-gray-800 rounded-lg mb-4">
    <div className="flex justify-between items-start mb-3">
      <div>
        <h3 className="text-xl font-bold text-white">{city} Forecast</h3>
        <p className="text-gray-400 text-sm">{shortForecast || 'Loading forecast...'}</p>
      </div>
      <div className="text-right">
        <DataSourceBadge source={source} cached={cached} />
        <p className="text-xs text-gray-500 mt-1">
          {cacheAge > 0 ? `${Math.floor(cacheAge / 60)}m ago` : 'Just fetched'}
        </p>
      </div>
    </div>

    <div className="grid grid-cols-3 gap-4">
      <div className="text-center p-3 bg-gray-700/50 rounded">
        <div className="text-3xl font-bold text-red-400">{forecastHigh}°F</div>
        <div className="text-xs text-gray-400 mt-1">High</div>
      </div>
      <div className="text-center p-3 bg-gray-700/50 rounded">
        <div className="text-3xl font-bold text-blue-400">{forecastLow}°F</div>
        <div className="text-xs text-gray-400 mt-1">Low</div>
      </div>
      <div className="text-center p-3 bg-gray-700/50 rounded">
        <div className="text-lg font-semibold text-white capitalize">{weatherPattern}</div>
        <div className="text-xs text-gray-400 mt-1">Pattern</div>
      </div>
    </div>

    <button
      onClick={onRefresh}
      disabled={refreshing}
      className="mt-3 w-full py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded text-white text-sm transition-colors"
    >
      {refreshing ? 'Refreshing...' : 'Refresh Forecast'}
    </button>
  </div>
);

interface BracketRowProps {
  bracket: BracketPrediction;
  onSelect: (bracket: BracketPrediction) => void;
}

const BracketRow: React.FC<BracketRowProps> = ({ bracket, onSelect }) => {
  const edgeClass = bracket.probability_edge > 0.05
    ? 'text-green-400'
    : bracket.probability_edge < -0.05
    ? 'text-red-400'
    : 'text-gray-400';

  const actionClass = {
    buy_yes: 'bg-green-900/30 border-green-700',
    buy_no: 'bg-blue-900/30 border-blue-700',
    hold: 'bg-gray-800 border-gray-700',
    skip: 'bg-gray-800 border-gray-700 opacity-60',
  }[bracket.recommended_action] || 'bg-gray-800 border-gray-700';

  return (
    <div
      className={`p-3 rounded border cursor-pointer hover:brightness-110 transition-all ${actionClass}`}
      onClick={() => onSelect(bracket)}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-semibold text-white">{bracket.label}</div>
          <div className="text-xs text-gray-400">{bracket.ticker}</div>
        </div>
        <div className="text-right">
          <div className={`font-bold ${edgeClass}`}>
            {bracket.probability_edge > 0 ? '+' : ''}
            {(bracket.probability_edge * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-400">Edge</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <div className="text-gray-400 text-xs">Model</div>
          <div className="text-white">{(bracket.model_probability * 100).toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-gray-400 text-xs">Market</div>
          <div className="text-white">{(bracket.market_implied_probability * 100).toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-gray-400 text-xs">Price</div>
          <div className="text-white">{bracket.yes_price_cents || '-'}¢</div>
        </div>
      </div>

      {bracket.recommended_action !== 'hold' && bracket.recommended_action !== 'skip' && (
        <div className="mt-2 pt-2 border-t border-gray-700">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">
              {bracket.recommended_action === 'buy_yes' ? 'Buy YES' : 'Buy NO'}
            </span>
            <span className="text-green-400">
              EV: {bracket.yes_ev_after_fee > bracket.no_ev_after_fee
                ? bracket.yes_ev_after_fee.toFixed(1)
                : bracket.no_ev_after_fee.toFixed(1)}¢
            </span>
          </div>
          <div className="flex justify-between text-xs mt-1">
            <span className="text-gray-500">
              Kelly: {(bracket.kelly_fraction * 100).toFixed(1)}%
            </span>
            <span className="text-gray-500">
              Size: {bracket.recommended_contracts} contracts
            </span>
          </div>
        </div>
      )}

      {bracket.position_conflict && (
        <div className="mt-2 text-xs text-red-400 bg-red-900/30 p-2 rounded">
          Position conflict: Already have {bracket.existing_side} position
        </div>
      )}
    </div>
  );
};

interface ProbabilityBarProps {
  brackets: BracketPrediction[];
}

const ProbabilityBar: React.FC<ProbabilityBarProps> = ({ brackets }) => {
  const colors = [
    'bg-red-500',
    'bg-orange-500',
    'bg-yellow-500',
    'bg-green-500',
    'bg-teal-500',
    'bg-blue-500',
    'bg-indigo-500',
    'bg-purple-500',
  ];

  return (
    <div className="mb-4">
      <div className="flex rounded overflow-hidden h-4">
        {brackets.map((b, i) => (
          <div
            key={b.ticker}
            className={`${colors[i % colors.length]} relative group`}
            style={{ width: `${b.model_probability * 100}%`, minWidth: '2px' }}
          >
            <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
              {b.label}: {(b.model_probability * 100).toFixed(1)}%
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>0%</span>
        <span>Total: {(brackets.reduce((acc, b) => acc + b.model_probability, 0) * 100).toFixed(1)}%</span>
        <span>100%</span>
      </div>
    </div>
  );
};

// ============ Main Component ============

interface PredictionPanelInnerProps {
  city: string;
}

const PredictionPanelInner: React.FC<PredictionPanelInnerProps> = ({ city }) => {
  const {
    data,
    error,
    isLoading,
    isStale,
    dataSource: _dataSource,  // Unused but available if needed
    cacheAge,
    forceRefresh,
  } = usePredictions(city);

  const [selectedBracket, setSelectedBracket] = useState<BracketPrediction | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await forceRefresh();
    } finally {
      setRefreshing(false);
    }
  }, [forceRefresh]);

  if (isLoading && !data) {
    return <LoadingSkeleton />;
  }

  if (error && !data) {
    return (
      <div className="p-4 bg-red-900/30 border border-red-700 rounded-lg">
        <h3 className="text-red-400 font-semibold mb-2">Failed to load predictions</h3>
        <p className="text-red-300 text-sm">{error}</p>
        <button
          onClick={handleRefresh}
          className="mt-3 px-3 py-1 bg-red-700 hover:bg-red-600 text-white rounded text-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 bg-gray-800 rounded-lg text-gray-400 text-center">
        No prediction data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stale Warning (Issue #16) */}
      {isStale && <StaleWarning cacheAge={cacheAge} />}

      {/* Forecast Header */}
      <ForecastHeader
        city={data.city}
        forecastHigh={data.forecast.forecast_high}
        forecastLow={data.forecast.forecast_low}
        weatherPattern={data.forecast.weather_pattern}
        shortForecast={data.forecast.short_forecast}
        source={data.forecast.source}
        cached={data.forecast.cached}
        cacheAge={cacheAge}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      {/* Warnings */}
      {data.warnings.length > 0 && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
          {data.warnings.map((w, i) => (
            <div key={i} className="text-yellow-400 text-sm">
              {w}
            </div>
          ))}
        </div>
      )}

      {/* Probability Visualization */}
      {data.brackets.length > 0 && <ProbabilityBar brackets={data.brackets} />}

      {/* Opportunities Summary */}
      {data.has_opportunities && data.best_opportunity && (
        <div className="p-3 bg-green-900/30 border border-green-700 rounded-lg">
          <div className="font-semibold text-green-400">Best Opportunity</div>
          <div className="text-white mt-1">
            {data.best_opportunity.label} - {data.best_opportunity.recommended_action === 'buy_yes' ? 'Buy YES' : 'Buy NO'} @ {data.best_opportunity.yes_price_cents || data.best_opportunity.no_price_cents}¢
          </div>
          <div className="text-sm text-gray-400">
            Edge: {(data.best_opportunity.probability_edge * 100).toFixed(1)}% |
            EV: {Math.max(data.best_opportunity.yes_ev_after_fee, data.best_opportunity.no_ev_after_fee).toFixed(1)}¢
          </div>
        </div>
      )}

      {/* Brackets Grid */}
      {data.brackets.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {data.brackets.map((bracket) => (
            <BracketRow
              key={bracket.ticker}
              bracket={bracket}
              onSelect={setSelectedBracket}
            />
          ))}
        </div>
      ) : (
        <div className="p-4 bg-gray-800 rounded-lg text-gray-400 text-center">
          No open bracket markets for this city
        </div>
      )}

      {/* Selected Bracket Detail */}
      {selectedBracket && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedBracket(null)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-bold text-white mb-4">{selectedBracket.label}</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Ticker</span>
                <span className="text-white font-mono">{selectedBracket.ticker}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Model Probability</span>
                <span className="text-white">{(selectedBracket.model_probability * 100).toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Market Probability</span>
                <span className="text-white">{(selectedBracket.market_implied_probability * 100).toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Edge</span>
                <span className={selectedBracket.probability_edge > 0 ? 'text-green-400' : 'text-red-400'}>
                  {(selectedBracket.probability_edge * 100).toFixed(2)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">YES Price</span>
                <span className="text-white">{selectedBracket.yes_price_cents || '-'}¢</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">YES EV (after fee)</span>
                <span className={selectedBracket.yes_ev_after_fee > 0 ? 'text-green-400' : 'text-gray-400'}>
                  {selectedBracket.yes_ev_after_fee.toFixed(2)}¢
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">NO EV (after fee)</span>
                <span className={selectedBracket.no_ev_after_fee > 0 ? 'text-green-400' : 'text-gray-400'}>
                  {selectedBracket.no_ev_after_fee.toFixed(2)}¢
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Kelly Fraction</span>
                <span className="text-white">{(selectedBracket.kelly_fraction * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Recommended</span>
                <span className="text-white capitalize">{selectedBracket.recommended_action.replace('_', ' ')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Confidence</span>
                <span className="text-white">{(selectedBracket.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
            <button
              onClick={() => setSelectedBracket(null)}
              className="mt-4 w-full py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ============ Exported Component with Error Boundary ============

interface PredictionPanelProps {
  city: string;
}

export const PredictionPanel: React.FC<PredictionPanelProps> = ({ city }) => (
  <PredictionErrorBoundary>
    <PredictionPanelInner city={city} />
  </PredictionErrorBoundary>
);

// ============ City Selector Component ============

interface CitySelectorProps {
  selectedCity: string;
  onCityChange: (city: string) => void;
}

export const CitySelector: React.FC<CitySelectorProps> = ({
  selectedCity,
  onCityChange,
}) => {
  const { cities, isLoading } = useSupportedCities();

  if (isLoading) {
    return (
      <div className="animate-pulse h-10 bg-gray-700 rounded w-40"></div>
    );
  }

  return (
    <select
      value={selectedCity}
      onChange={(e) => onCityChange(e.target.value)}
      className="px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {cities.map((city) => (
        <option key={city.code} value={city.code}>
          {city.code}
        </option>
      ))}
    </select>
  );
};

export default PredictionPanel;
