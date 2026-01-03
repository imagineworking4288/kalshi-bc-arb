import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import {
  WeatherStatus,
  CityResult,
  getCostStatus,
  getCostColor,
  getCostBgColor
} from '../../types/weather';

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

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-700/50 text-left">
              <th className="p-3">Bracket</th>
              <th className="p-3 text-right">YES Ask</th>
              <th className="p-3 text-right">YES Bid</th>
              <th className="p-3 text-right">Volume</th>
              <th className="p-3">Notes</th>
            </tr>
          </thead>
          <tbody>
            {series.brackets && series.brackets.length > 0 ? (
              series.brackets.map((bracket: any) => {
                // Smart bracket label extraction from title
                const getBracketLabel = (): string => {
                  if (bracket.title) {
                    const title = bracket.title;

                    // Match "32-33°" or "32-33°F"
                    const rangeMatch = title.match(/(\d+)\s*[-–]\s*(\d+)°/);
                    if (rangeMatch) {
                      return `${rangeMatch[1]}–${rangeMatch[2]}°F`;
                    }

                    // Match ">35°" or ">=35°" or "be >35°"
                    const gtMatch = title.match(/>\s*=?\s*(\d+)°/);
                    if (gtMatch) {
                      return `≥${gtMatch[1]}°F`;
                    }

                    // Match "<28°" or "<=28°" or "be <28°"
                    const ltMatch = title.match(/<\s*=?\s*(\d+)°/);
                    if (ltMatch) {
                      return `≤${ltMatch[1]}°F`;
                    }
                  }

                  // Fallback to ticker suffix
                  return bracket.ticker?.split('-').pop() || 'Unknown';
                };

                // Parse temps for forecast matching
                const getParsedTemps = (): { low: number | null; high: number | null } => {
                  if (bracket.title) {
                    const rangeMatch = bracket.title.match(/(\d+)\s*[-–]\s*(\d+)°/);
                    if (rangeMatch) {
                      return { low: parseInt(rangeMatch[1]), high: parseInt(rangeMatch[2]) };
                    }
                    const gtMatch = bracket.title.match(/>\s*=?\s*(\d+)°/);
                    if (gtMatch) {
                      return { low: parseInt(gtMatch[1]), high: null };
                    }
                    const ltMatch = bracket.title.match(/<\s*=?\s*(\d+)°/);
                    if (ltMatch) {
                      return { low: null, high: parseInt(ltMatch[1]) };
                    }
                  }
                  return { low: null, high: null };
                };

                // Check if forecast falls in this bracket
                const temps = getParsedTemps();
                const isForecastBracket = forecastTemp != null && (() => {
                  const { low, high } = temps;
                  if (low !== null && high !== null) {
                    return forecastTemp >= low && forecastTemp <= high;
                  }
                  if (low !== null && high === null) {
                    return forecastTemp >= low;
                  }
                  if (low === null && high !== null) {
                    return forecastTemp <= high;
                  }
                  return false;
                })();

                return (
                  <tr
                    key={bracket.ticker}
                    className={`border-t border-gray-700 transition-colors ${
                      isForecastBracket ? 'bg-blue-500/30 border-l-4 border-l-blue-400' : ''
                    }`}
                  >
                    <td className="p-3 font-mono text-sm">
                      {getBracketLabel()}
                    </td>
                    <td className="p-3 text-right text-green-400 font-medium">
                      {bracket.yes_ask ?? 0}¢
                    </td>
                    <td className="p-3 text-right text-gray-400">
                      {bracket.yes_bid ?? 0}¢
                    </td>
                    <td className="p-3 text-right text-gray-400">
                      {(bracket.volume ?? 0).toLocaleString()}
                    </td>
                    <td className="p-3 text-sm text-blue-400">
                      {isForecastBracket && `← Forecast: ${forecastTemp}°F`}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={5} className="p-8 text-center text-gray-400">
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
                {series.best_cost != null ? `${series.best_cost}c` : '-'}
              </td>
              <td className="p-3"></td>
              <td className="p-3"></td>
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
          <span>Series: {series.series}</span>
          <span>{series.bracket_count} brackets</span>
          {forecastTemp != null && <span>NWS Forecast: {forecastTemp}F</span>}
        </div>
      </div>
    </div>
  );
}

export { WeatherArbitrageSection };
