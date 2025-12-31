import { useTradingStore } from '../../stores/tradingStore';
import { useSpotPrice } from '../../hooks/useSpotPrice';
import { formatPrice, formatCurrency } from '../../utils/format';

function LiveIndicator({ isLive }: { isLive: boolean }) {
  if (!isLive) {
    return (
      <span className="inline-flex h-2 w-2 rounded-full bg-yellow-500" title="Data may be stale" />
    );
  }

  return (
    <span className="relative flex h-2 w-2" title="Live">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
    </span>
  );
}

export function Header() {
  const mode = useTradingStore((s) => s.mode);
  const balance = useTradingStore((s) => s.balance);
  const { data: spotPrice, isLoading: priceLoading } = useSpotPrice();

  return (
    <header className="bg-gray-800 border-b border-gray-700">
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold">Kalshi Trading Platform</h1>
          </div>

          <div className="flex items-center gap-6 text-sm">
            {priceLoading ? (
              <div className="text-gray-400">Loading BTC...</div>
            ) : spotPrice ? (
              <div className="flex items-center gap-2">
                <LiveIndicator isLive={spotPrice.isLive} />
                <span className="text-gray-400">BTC:</span>
                <span className="font-medium">{formatPrice(spotPrice.price)}</span>
                <span className="text-gray-500 text-xs">via {spotPrice.source}</span>
              </div>
            ) : (
              <div className="text-gray-500">BTC: unavailable</div>
            )}
          </div>

          <div className="text-right">
            <div className="text-sm text-gray-400">Paper Balance</div>
            <div className="font-medium">
              {balance ? formatCurrency(balance.available_balance) : '$0.00'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
