import { TradeCard } from './TradeCard';

export function TradeTab() {
  // Hardcoded test ticker - valid BTC market
  const testTicker = 'KXBTCD-26JAN0217-T99249.99';

  return (
    <div className="space-y-6">
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
        <h2 className="text-lg font-bold mb-2">Manual Trading (MVP)</h2>
        <p className="text-sm text-gray-400">
          This is a minimal test interface. Place trades in paper mode (simulation) or live mode (real money) by checking the boxes below.
        </p>
      </div>

      <div className="max-w-2xl">
        <TradeCard ticker={testTicker} />
      </div>

      <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-4 text-sm text-blue-200">
        <div className="font-medium mb-1">Dual-Mode Trading</div>
        <div>
          You can execute the same trade in both paper and live mode simultaneously by checking both boxes.
          Paper trades are simulated using your paper balance. Live trades use real Kalshi API calls.
        </div>
      </div>
    </div>
  );
}
