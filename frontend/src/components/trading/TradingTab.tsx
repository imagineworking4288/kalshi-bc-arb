import { useTradingStore } from '../../stores/tradingStore';
import { ModeToggle } from './ModeToggle';
import { ModeBanner } from './ModeBanner';
import { PositionList } from './PositionList';
import { TradeHistory } from './TradeHistory';
import { formatCurrency } from '../../utils/format';

export function TradingTab() {
  const mode = useTradingStore((s) => s.mode);
  const balance = useTradingStore((s) => s.balance);
  const positions = useTradingStore((s) => s.positions);

  return (
    <div className="space-y-6">
      <ModeToggle />
      <ModeBanner />

      <div className="bg-gray-800 rounded-lg p-4">
        <div className="flex justify-between items-center">
          <div>
            <div className="text-sm text-gray-400">
              {mode === 'paper' ? 'Paper Balance' : 'Kalshi Balance'}
            </div>
            <div className="text-2xl font-bold">
              {formatCurrency(balance?.available_balance || 0)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Open Positions</div>
            <div className="text-2xl font-bold">{positions.length}</div>
          </div>
        </div>
      </div>

      <PositionList />
      <TradeHistory />
    </div>
  );
}
