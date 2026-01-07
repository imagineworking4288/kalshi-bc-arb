import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  WeatherStatus,
  CityResult,
  BracketMarket,
  getCostStatus,
  getCostColor,
  getCostBgColor
} from '../../types/weather';
import { ArbitrageAnalysisBox } from './ArbitrageAnalysisBox';

const CITIES = ['NYC', 'LAX', 'CHI', 'MIA', 'DEN', 'AUS', 'PHL'];

const CITY_NAMES: Record<string, string> = {
  NYC: 'New York',
  LAX: 'Los Angeles',
  CHI: 'Chicago',
  MIA: 'Miami',
  DEN: 'Denver',
  AUS: 'Austin',
  PHL: 'Philadelphia'
};

// Extract temperature label directly from Kalshi's title field
// This guarantees exact matching with Kalshi website display
function getBracketLabel(bracket: BracketMarket): string {
  const title = bracket.title || '';

  // Extract pattern after "be " and before "°"
  // Examples: "be 61-62°" → "61-62", "be >62°" → ">62", "be <55°" → "<55"
  const match = title.match(/be\s+([<>]=?)?\s*(\d+)(?:-(\d+))?°/);

  if (match) {
    const [, operator, num1, num2] = match;

    if (num2) {
      // Range like "61-62°" → "61-62°F"
      return `${num1}-${num2}°F`;
    } else if (operator === '>') {
      // Greater than like ">62°" means "63 or above" → "≥63°F"
      return `≥${parseInt(num1) + 1}°F`;
    } else if (operator === '>=') {
      // Greater than or equal like ">=62°" → "≥62°F"
      return `≥${num1}°F`;
    } else if (operator === '<') {
      // Less than like "<55°" means "54 or below" → "≤54°F"
      return `≤${parseInt(num1) - 1}°F`;
    } else if (operator === '<=') {
      // Less than or equal like "<=55°" → "≤55°F"
      return `≤${num1}°F`;
    } else {
      // Single value
      return `${num1}°F`;
    }
  }

  // Fallback: try to extract any temperature pattern
  const fallbackMatch = title.match(/(\d+)(?:-(\d+))?°/);
  if (fallbackMatch) {
    const [, n1, n2] = fallbackMatch;
    return n2 ? `${n1}-${n2}°F` : `${n1}°F`;
  }

  return bracket.title?.slice(0, 20) || '?';
}

// Sort brackets by temperature ascending (open-ended lower first, then ranges, then open-ended upper)
function sortBrackets(brackets: BracketMarket[]): BracketMarket[] {
  return [...brackets].sort((a, b) => {
    // Open-ended lower brackets (≤X) should come first
    const aVal = a.floor_strike ?? (a.cap_strike !== null ? -Infinity : Infinity);
    const bVal = b.floor_strike ?? (b.cap_strike !== null ? -Infinity : Infinity);
    return aVal - bVal;
  });
}

// Check if forecast temperature falls within this bracket
// Note: Kalshi uses floor (inclusive) and cap (exclusive)
function isForecastInBracket(bracket: BracketMarket, forecastTemp: number): boolean {
  const floor = bracket.floor_strike ?? -Infinity;
  const cap = bracket.cap_strike ?? Infinity;

  // Temperature must be >= floor AND < cap (cap is exclusive)
  return forecastTemp >= floor && forecastTemp < cap;
}

export default function WeatherArbitrageSection() {
  const [status, setStatus] = useState<WeatherStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCity, setExpandedCity] = useState<string | null>(null);
  const [expandedType, setExpandedType] = useState<'high' | 'low'>('high');

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getWeatherStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error && !status) {
    return (
      <div className="bg-red-500/20 border border-red-500 rounded-lg p-4">
        <p className="text-red-400">Error: {error}</p>
        <button onClick={fetchStatus} className="mt-2 px-4 py-2 bg-red-600 rounded hover:bg-red-700">
          Retry
        </button>
      </div>
    );
  }

  // Calculate total brackets scanned
  const totalScanned = Object.values(status?.cities ?? {}).reduce((sum, city) => {
    return sum + (city?.high?.bracket_count ?? 0) + (city?.low?.bracket_count ?? 0);
  }, 0);

  return (
    <div className="space-y-6">
      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className={`text-2xl font-bold ${status?.stats?.total_arbitrage ? 'text-green-400' : 'text-gray-400'}`}>
            {status?.stats?.total_arbitrage ?? 0}
          </div>
          <div className="text-sm text-gray-400">Opportunities</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className={`text-2xl font-bold ${status?.stats?.total_near_miss ? 'text-yellow-400' : 'text-gray-400'}`}>
            {status?.stats?.total_near_miss ?? 0}
          </div>
          <div className="text-sm text-gray-400">Near Misses</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-2xl font-bold text-blue-400">{totalScanned}</div>
          <div className="text-sm text-gray-400">Markets Scanned</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-2xl font-bold text-gray-400">
            {status?.last_scan ? new Date(status.last_scan).toLocaleTimeString() : '-'}
          </div>
          <div className="text-sm text-gray-400">Last Scan</div>
        </div>
      </div>

      {/* Opportunities Alert */}
      {status?.opportunities && status.opportunities.length > 0 && (
        <div className="bg-green-500/20 border border-green-500 rounded-lg p-4">
          <h3 className="text-green-400 font-bold text-lg mb-2">
            [TARGET] {status.opportunities.length} Arbitrage Opportunity Found!
          </h3>
          {status.opportunities.map((opp, i) => (
            <div key={i} className="text-green-300">
              {opp.city_name} {opp.market_type.toUpperCase()}: Buy all for {opp.total_cost}c -
              Net Profit: {opp.net_profit}c
            </div>
          ))}
        </div>
      )}

      {/* City Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        {CITIES.map(code => {
          const city = status?.cities?.[code];
          const forecast = status?.forecasts?.[code];
          const highStatus = getCostStatus(city?.high?.best_cost ?? null);
          const lowStatus = getCostStatus(city?.low?.best_cost ?? null);

          return (
            <div
              key={code}
              className={`bg-gray-800 rounded-lg p-4 border transition-all ${
                expandedCity === code ? 'border-blue-500 ring-2 ring-blue-500/50' : 'border-gray-700'
              }`}
            >
              <div className="text-center mb-3">
                <div className="font-bold text-lg">{code}</div>
                <div className="text-xs text-gray-400">{CITY_NAMES[code]}</div>
              </div>

              {forecast ? (
                <div className="text-center mb-3 py-2 bg-gray-700/50 rounded">
                  <div className="text-sm">
                    <span className="text-red-400">H: {forecast.high}F</span>
                    {' / '}
                    <span className="text-blue-400">L: {forecast.low}F</span>
                  </div>
                </div>
              ) : (
                <div className="text-center mb-3 py-2 bg-gray-700/50 rounded">
                  <div className="text-xs text-gray-500">No forecast</div>
                </div>
              )}

              <button
                onClick={() => { setExpandedCity(expandedCity === code ? null : code); setExpandedType('high'); }}
                className={`w-full mb-2 p-2 rounded border text-sm font-medium ${getCostBgColor(highStatus)}`}
              >
                <div className="flex justify-between">
                  <span>HIGH</span>
                  <span className={getCostColor(highStatus)}>
                    {city?.high?.best_cost != null ? `${city.high.best_cost}c` : '-'}
                  </span>
                </div>
              </button>

              <button
                onClick={() => { setExpandedCity(expandedCity === code ? null : code); setExpandedType('low'); }}
                className={`w-full p-2 rounded border text-sm font-medium ${getCostBgColor(lowStatus)}`}
              >
                <div className="flex justify-between">
                  <span>LOW</span>
                  <span className={getCostColor(lowStatus)}>
                    {city?.low?.best_cost != null ? `${city.low.best_cost}c` : '-'}
                  </span>
                </div>
              </button>

              <div className="text-center mt-2 text-xs text-gray-500">
                {(city?.high?.bracket_count ?? 0) + (city?.low?.bracket_count ?? 0)} markets
              </div>
            </div>
          );
        })}
      </div>

      {/* Expanded Bracket Table */}
      {expandedCity && status?.cities?.[expandedCity] && (
        <BracketTable
          city={status.cities[expandedCity]}
          type={expandedType}
          onTypeChange={setExpandedType}
          onClose={() => setExpandedCity(null)}
        />
      )}
    </div>
  );
}

function BracketTable({
  city,
  type,
  onTypeChange,
  onClose
}: {
  city: CityResult;
  type: 'high' | 'low';
  onTypeChange: (type: 'high' | 'low') => void;
  onClose: () => void;
}) {
  const series = type === 'high' ? city.high : city.low;
  if (!series) return null;

  const forecastTemp = series.forecast?.adjusted_temp;
  const costStatus = getCostStatus(series.best_cost);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <div className="flex items-center gap-4">
          <h3 className="font-bold text-lg">{city.city} {type.toUpperCase()} Temperature</h3>
          <div className="flex rounded-lg overflow-hidden border border-gray-600">
            <button
              onClick={() => onTypeChange('high')}
              className={`px-3 py-1 text-sm ${type === 'high' ? 'bg-red-600 text-white' : 'bg-gray-700 text-gray-400'}`}
            >
              HIGH
            </button>
            <button
              onClick={() => onTypeChange('low')}
              className={`px-3 py-1 text-sm ${type === 'low' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'}`}
            >
              LOW
            </button>
          </div>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-white p-1">X</button>
      </div>

      {/* Arbitrage Analysis Box */}
      {series.arbitrage && (
        <div className="p-4 border-b border-gray-700">
          <ArbitrageAnalysisBox key={`${city.code}-${type}`} arbitrage={series.arbitrage} />
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-700/50 text-left">
              <th className="p-3">Bracket</th>
              <th className="p-3 text-right text-cyan-400">YES Ask</th>
              <th className="p-3 text-right text-orange-400">NO Ask</th>
              <th className="p-3 text-right text-gray-400">YES Bid</th>
              <th className="p-3 text-right text-gray-400">NO Bid</th>
              <th className="p-3 text-right">Volume</th>
              <th className="p-3">Notes</th>
            </tr>
          </thead>
          <tbody>
            {series.brackets && series.brackets.length > 0 ? (
              sortBrackets(series.brackets).map((bracket) => {
                // Check if forecast falls in this bracket using floor_strike/cap_strike
                const isForecast = forecastTemp != null && isForecastInBracket(bracket, forecastTemp);

                return (
                  <tr
                    key={bracket.ticker}
                    className={`border-t border-gray-700 transition-colors ${
                      isForecast ? 'bg-blue-500/30 border-l-4 border-l-blue-400' : ''
                    }`}
                  >
                    <td className="p-3 font-mono text-sm">
                      {getBracketLabel(bracket)}
                    </td>
                    <td className="p-3 text-right text-cyan-400 font-medium">
                      {bracket.yes_ask ?? 0}¢
                    </td>
                    <td className="p-3 text-right text-orange-400 font-medium">
                      {bracket.no_ask ?? 0}¢
                    </td>
                    <td className="p-3 text-right text-gray-500">
                      {bracket.yes_bid ?? 0}¢
                    </td>
                    <td className="p-3 text-right text-gray-500">
                      {bracket.no_bid ?? 0}¢
                    </td>
                    <td className="p-3 text-right text-gray-400">
                      {(bracket.volume ?? 0).toLocaleString()}
                    </td>
                    <td className="p-3 text-sm text-blue-400">
                      {isForecast && `← Forecast: ${forecastTemp}°F`}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-400">
                  <div className="text-lg mb-2">No markets available</div>
                  <div className="text-sm">
                    {type === 'low'
                      ? 'Kalshi may not offer LOW temperature markets for this city/date'
                      : 'No bracket markets found for this series'
                    }
                  </div>
                </td>
              </tr>
            )}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-gray-600 bg-gray-700/50 font-bold">
              <td className="p-3">TOTAL</td>
              <td className={`p-3 text-right ${getCostColor(costStatus)}`}>
                {series.totals?.yes_ask != null ? `${series.totals.yes_ask}¢` : (series.best_cost != null ? `${series.best_cost}¢` : '-')}
              </td>
              <td className="p-3 text-right text-orange-400">
                {series.totals?.no_ask != null ? `${series.totals.no_ask}¢` : '-'}
              </td>
              <td className="p-3 text-right text-gray-500">
                {series.totals?.yes_bid != null ? `${series.totals.yes_bid}¢` : '-'}
              </td>
              <td className="p-3 text-right text-gray-500">
                {series.totals?.no_bid != null ? `${series.totals.no_bid}¢` : '-'}
              </td>
              <td className="p-3 text-right text-gray-400">
                {series.totals?.volume != null ? series.totals.volume.toLocaleString() : '-'}
              </td>
              <td className={`p-3 text-sm ${getCostColor(costStatus)}`}>
                {costStatus === 'opportunity' && '[TARGET] ARBITRAGE!'}
                {costStatus === 'near_miss' && '[FAST] Near Miss'}
                {costStatus === 'neutral' && 'No opportunity'}
                {costStatus === 'negative' && '[ERR] Negative edge'}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div className="p-4 border-t border-gray-700 bg-gray-700/30 text-sm text-gray-400">
        <div className="flex justify-between">
          <span>Series: {series.series || `${city.code}-${type.toUpperCase()}`}</span>
          <span>{series.bracket_count ?? series.brackets?.length ?? 0} brackets</span>
          {forecastTemp != null && <span>NWS Forecast: {forecastTemp}°F</span>}
        </div>
      </div>
    </div>
  );
}

export { WeatherArbitrageSection };
