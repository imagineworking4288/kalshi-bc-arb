import { useTradingStore } from '../../stores/tradingStore';
import { useOpportunityStore } from '../../stores/opportunityStore';
import { formatPrice, formatCurrency } from '../../utils/format';

export function Header() {
  const mode = useTradingStore((s) => s.mode);
  const balance = useTradingStore((s) => s.balance);
  const spotPrice = useOpportunityStore((s) => s.spotPrice);

  return (
    <header className="bg-gray-800 border-b border-gray-700">
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold">Kalshi Arb Scanner</h1>
            {mode === 'paper' ? (
              <span className="px-3 py-1 bg-blue-600 text-white text-sm font-medium rounded-full">
                PAPER
              </span>
            ) : (
              <span className="px-3 py-1 bg-red-600 text-white text-sm font-medium rounded-full animate-pulse">
                LIVE
              </span>
            )}
          </div>

          <div className="flex items-center gap-6 text-sm">
            {spotPrice && (
              <div>
                <span className="text-gray-400">BTC:</span>{' '}
                <span className="font-medium">{formatPrice(spotPrice)}</span>
              </div>
            )}
          </div>

          <div className="text-right">
            <div className="text-sm text-gray-400">
              {mode === 'paper' ? 'Paper Balance' : 'Balance'}
            </div>
            <div className="font-medium">
              {balance ? formatCurrency(balance.available_balance) : '$0.00'}
            </div>
          </div>
        </div>

        {mode === 'live' && (
          <div className="mt-3 p-2 bg-red-900/50 border border-red-600 rounded text-red-200 text-sm text-center">
            LIVE TRADING ENABLED - Real money will be used
          </div>
        )}
      </div>
    </header>
  );
}
