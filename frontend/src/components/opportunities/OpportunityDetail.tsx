import { ArrowUp, ArrowDown, AlertCircle, ExternalLink } from 'lucide-react';
import { useOpportunityStore } from '../../stores/opportunityStore';
import { useTradeStore } from '../../stores/tradeStore';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';

export function OpportunityDetail() {
  const opportunity = useOpportunityStore((s) => s.getSelectedOpportunity());
  const { openTradeModal } = useTradeStore();

  if (!opportunity) {
    return (
      <div className="bg-gray-800 rounded-lg p-8 text-center">
        <p className="text-gray-400">Select an opportunity to view details</p>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatPercent = (pct: number) => {
    return `${pct.toFixed(2)}%`;
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge>{opportunity.asset}</Badge>
            <h2 className="text-xl font-semibold text-white">
              {opportunity.thresholdDirection === 'above' ? (
                <ArrowUp className="w-5 h-5 inline text-emerald-500 mr-1" />
              ) : (
                <ArrowDown className="w-5 h-5 inline text-red-500 mr-1" />
              )}
              {formatCurrency(opportunity.thresholdStrike)}
            </h2>
          </div>
          <p className="text-sm text-gray-400">{opportunity.thresholdTitle}</p>
        </div>

        <Button onClick={() => openTradeModal(opportunity.id)}>Trade</Button>
      </div>

      {/* Profit summary */}
      <div className="bg-gray-700/50 rounded-lg p-4 mb-6">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-sm text-gray-500 mb-1">Net Profit</p>
            <p className="text-2xl font-bold text-emerald-400">
              {formatPercent(opportunity.netProfitPct)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Est. Fees</p>
            <p className="text-lg font-medium text-white">
              {formatCurrency(opportunity.estimatedFees)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-1">Max Liquidity</p>
            <p className="text-lg font-medium text-white">
              {formatCurrency(opportunity.maxLiquidityUsd)}
            </p>
          </div>
        </div>
      </div>

      {/* Price comparison */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
          Price Analysis
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Threshold Price</span>
            <span className="font-mono text-white">
              {(opportunity.thresholdYesPrice * 100).toFixed(1)}c
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Implied Price (from brackets)</span>
            <span className="font-mono text-white">
              {(opportunity.impliedPrice * 100).toFixed(1)}c
            </span>
          </div>
          <div className="flex items-center justify-between border-t border-gray-700 pt-3">
            <span className="text-gray-400">Divergence</span>
            <span
              className={`font-mono font-medium ${
                opportunity.divergence > 0 ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {opportunity.divergence > 0 ? '+' : ''}
              {(opportunity.divergence * 100).toFixed(1)}c
            </span>
          </div>
        </div>
      </div>

      {/* Spot price context */}
      {opportunity.spotPrice && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
            Spot Price Context
          </h3>
          <div className="bg-gray-700/50 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Current {opportunity.asset}</span>
              <span className="font-mono text-white">
                {formatCurrency(opportunity.spotPrice)}
              </span>
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-gray-400">Relative to Strike</span>
              <span
                className={`font-medium ${
                  opportunity.spotRelation === 'above'
                    ? 'text-emerald-400'
                    : 'text-red-400'
                }`}
              >
                {opportunity.spotRelation === 'above' ? '+' : '-'}
                {formatCurrency(opportunity.distanceFromThreshold || 0)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Required brackets */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">
          Required Brackets ({opportunity.requiredBrackets.length})
        </h3>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {opportunity.requiredBrackets.map((bracket) => (
            <div
              key={bracket.ticker}
              className="flex items-center justify-between p-2 bg-gray-700/50 rounded"
            >
              <span className="text-sm text-gray-300 truncate flex-1">
                {formatCurrency(bracket.lowBound)} -{' '}
                {formatCurrency(bracket.highBound)}
              </span>
              <span className="font-mono text-sm text-white ml-2">
                {(bracket.yesAsk * 100).toFixed(0)}c
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Trade direction */}
      <div className="p-3 bg-blue-900/20 border border-blue-700 rounded-lg">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-blue-400">Trade Direction</p>
            <p className="text-sm text-gray-400 mt-1">
              {opportunity.tradeDirection === 'buy_brackets'
                ? 'Buy YES on all brackets to capture mispricing'
                : 'Buy YES on threshold (underpriced relative to brackets)'}
            </p>
          </div>
        </div>
      </div>

      {/* View on Kalshi link */}
      <div className="mt-4 text-center">
        <a
          href={`https://kalshi.com/markets/${opportunity.thresholdTicker}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-gray-400 hover:text-white inline-flex items-center gap-1"
        >
          View on Kalshi
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}
