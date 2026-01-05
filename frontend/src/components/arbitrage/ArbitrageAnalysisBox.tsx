import { ArbitrageAnalysis, ArbitrageStrategy } from '../../types/weather';

interface Props {
  arbitrage: ArbitrageAnalysis;
}

interface StrategyCardProps {
  label: string;
  strategy: ArbitrageStrategy;
  isBest: boolean;
}

function StrategyCard({ label, strategy, isBest }: StrategyCardProps) {
  const isArb = strategy.is_arb;

  return (
    <div
      className={`flex-1 p-3 rounded-lg border transition-all ${
        isArb
          ? isBest
            ? 'bg-green-500/20 border-green-500 shadow-lg shadow-green-500/20'
            : 'bg-green-500/10 border-green-500/50'
          : 'bg-gray-800/50 border-gray-700'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`font-semibold text-sm ${isArb ? 'text-green-400' : 'text-gray-400'}`}>
          {label}
        </span>
        {isBest && (
          <span className="text-xs bg-green-500 text-black px-2 py-0.5 rounded font-bold">
            BEST
          </span>
        )}
      </div>

      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Cost:</span>
          <span className="text-gray-300">{strategy.cost}¢</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Payout:</span>
          <span className="text-gray-300">{strategy.payout}¢</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">P/L:</span>
          <span className={`font-semibold ${
            strategy.profit > 0 ? 'text-green-400' :
            strategy.profit < 0 ? 'text-red-400' : 'text-gray-400'
          }`}>
            {strategy.profit > 0 ? '+' : ''}{strategy.profit}¢
            {isArb ? ' ✅' : ' ❌'}
          </span>
        </div>
      </div>
    </div>
  );
}

export function ArbitrageAnalysisBox({ arbitrage }: Props) {
  const strategies: { key: keyof ArbitrageAnalysis; label: string }[] = [
    { key: 'all_yes', label: 'ALL YES' },
    { key: 'all_no', label: 'ALL NO' },
    { key: 'min_2_no', label: 'MIN 2-NO' },
  ];

  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Arbitrage Analysis
      </h3>
      <div className="flex gap-2">
        {strategies.map(({ key, label }) => {
          const strategy = arbitrage[key] as ArbitrageStrategy;
          return (
            <StrategyCard
              key={key}
              label={label}
              strategy={strategy}
              isBest={arbitrage.best_strategy === key}
            />
          );
        })}
      </div>

      {/* Min 2-NO Details */}
      {arbitrage.min_2_no.brackets && arbitrage.min_2_no.brackets.length === 2 && (
        <div className="mt-2 text-xs text-gray-500">
          Min 2-NO brackets: {arbitrage.min_2_no.brackets[0].title} ({arbitrage.min_2_no.brackets[0].no_ask}¢)
          {' + '}
          {arbitrage.min_2_no.brackets[1].title} ({arbitrage.min_2_no.brackets[1].no_ask}¢)
        </div>
      )}
    </div>
  );
}

export default ArbitrageAnalysisBox;
