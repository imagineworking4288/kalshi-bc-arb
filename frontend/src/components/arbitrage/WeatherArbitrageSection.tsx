export function WeatherArbitrageSection() {
  const cities = [
    { name: 'New York City', code: 'NYC', icon: '🗽', color: 'from-blue-900/30 to-indigo-900/30', borderColor: 'border-blue-500/50' },
    { name: 'Chicago', code: 'CHI', icon: '🌆', color: 'from-cyan-900/30 to-blue-900/30', borderColor: 'border-cyan-500/50' },
    { name: 'Miami', code: 'MIA', icon: '🌴', color: 'from-orange-900/30 to-red-900/30', borderColor: 'border-orange-500/50' },
    { name: 'Austin', code: 'AUS', icon: '🎸', color: 'from-purple-900/30 to-pink-900/30', borderColor: 'border-purple-500/50' },
    { name: 'Los Angeles', code: 'LAX', icon: '🌞', color: 'from-yellow-900/30 to-orange-900/30', borderColor: 'border-yellow-500/50' },
    { name: 'Denver', code: 'DEN', icon: '🏔️', color: 'from-green-900/30 to-teal-900/30', borderColor: 'border-green-500/50' }
  ];

  return (
    <div className="space-y-4">
      {/* Explanation Banner */}
      <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 border border-blue-500/30 rounded-lg p-4">
        <h3 className="text-lg font-bold text-white mb-2">🌡️ Weather Temperature Arbitrage</h3>
        <p className="text-sm text-gray-300 mb-2">
          Buy all temperature brackets for a city when the total cost is less than 100¢ for guaranteed profit.
        </p>
        <div className="text-xs text-gray-400">
          <strong>Strategy:</strong> Each city has 6 temperature brackets. If you can buy YES on all 6 for less than $1 total,
          you're guaranteed a $1 payout regardless of the actual temperature, netting a risk-free profit.
        </div>
      </div>

      {/* City Cards Grid */}
      <div className="grid grid-cols-3 gap-4">
        {cities.map((city) => (
          <div
            key={city.code}
            className={`bg-gradient-to-br ${city.color} border ${city.borderColor} rounded-lg p-4 relative overflow-hidden`}
          >
            {/* Coming Soon Badge */}
            <div className="absolute top-2 right-2">
              <span className="px-2 py-1 bg-yellow-600/80 text-yellow-100 text-xs font-bold rounded">
                COMING SOON
              </span>
            </div>

            {/* City Icon */}
            <div className="text-4xl mb-2">{city.icon}</div>

            {/* City Name */}
            <h4 className="text-lg font-bold text-white mb-1">{city.name}</h4>
            <p className="text-xs text-gray-400 mb-3">Market Code: {city.code}</p>

            {/* Placeholder Stats */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Brackets:</span>
                <span className="text-gray-500">-</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Best Cost:</span>
                <span className="text-gray-500">-</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Opportunities:</span>
                <span className="text-gray-500">0</span>
              </div>
            </div>

            {/* Placeholder Button */}
            <button
              disabled
              className="w-full mt-3 py-2 bg-slate-700/50 text-gray-500 rounded text-sm font-medium cursor-not-allowed"
            >
              Scanner Disabled
            </button>
          </div>
        ))}
      </div>

      {/* Info Section */}
      <div className="bg-slate-800 rounded-lg p-4">
        <h4 className="text-sm font-bold text-white mb-2">How Weather Arbitrage Works</h4>
        <div className="text-xs text-gray-400 space-y-2">
          <p>
            <strong className="text-white">1. Temperature Brackets:</strong> Each city has markets for different temperature ranges
            (e.g., "Will NYC be 60-65°F?", "Will NYC be 65-70°F?", etc.)
          </p>
          <p>
            <strong className="text-white">2. Arbitrage Opportunity:</strong> If you can buy YES on all 6 brackets for a total less than $1.00,
            you have a guaranteed profit because exactly one bracket must resolve to YES.
          </p>
          <p>
            <strong className="text-white">3. Example:</strong> If brackets cost 15¢ + 16¢ + 18¢ + 17¢ + 16¢ + 15¢ = 97¢ total,
            you spend 97¢ and receive $1.00 payout for a 3¢ guaranteed profit.
          </p>
          <p className="text-yellow-400 mt-3">
            🚧 This feature is under development. Scanner will automatically detect these opportunities across all 6 cities.
          </p>
        </div>
      </div>
    </div>
  );
}

export default WeatherArbitrageSection;
