import { useTradingStore } from '../../stores/tradingStore';
import { formatPrice, formatTimeRemaining } from '../../utils/format';
import type { Opportunity } from '../../types';
import clsx from 'clsx';

interface Props {
  opportunity: Opportunity;
}

export function OpportunityCard({ opportunity: opp }: Props) {
  const mode = useTradingStore((s) => s.mode);
  const openExecuteModal = useTradingStore((s) => s.openExecuteModal);

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-semibold text-lg">{opp.threshold_title}</h3>
          <p className="text-gray-400 text-sm">
            {opp.bracket_count} brackets - Settles in {formatTimeRemaining(opp.settlement_time)}
          </p>
          {opp.spot_price && (
            <p className="text-sm mt-1">
              BTC: {formatPrice(opp.spot_price)}
              {opp.spot_price > opp.threshold_strike ? (
                <span className="text-green-400 ml-2">Above</span>
              ) : (
                <span className="text-red-400 ml-2">Below</span>
              )}
            </p>
          )}
        </div>

        <div className="text-right">
          <div className={clsx(
            'text-2xl font-bold',
            opp.net_profit_pct >= 5 ? 'text-green-400' :
            opp.net_profit_pct >= 3 ? 'text-yellow-400' : 'text-gray-300'
          )}>
            +{opp.net_profit_pct.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-400">
            ${opp.max_liquidity_usd.toLocaleString()} available
          </div>
        </div>
      </div>

      <div className="mt-4 p-3 bg-gray-700 rounded">
        <div className="text-sm text-gray-400 mb-2">Per contract set:</div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Cost:</span>
            <span className="ml-2">${opp.cost_per_set.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-gray-400">Fees:</span>
            <span className="ml-2">${opp.fees_per_set.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-gray-400">Profit:</span>
            <span className="ml-2 text-green-400">${opp.profit_per_set.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <button
        onClick={() => openExecuteModal(opp)}
        className={clsx(
          'w-full mt-4 py-3 rounded-lg font-bold text-white transition-colors',
          mode === 'paper'
            ? 'bg-blue-600 hover:bg-blue-700'
            : 'bg-red-600 hover:bg-red-700'
        )}
      >
        EXECUTE FULL ARBITRAGE
      </button>
    </div>
  );
}
