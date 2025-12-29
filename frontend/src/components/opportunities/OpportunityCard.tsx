import { ArrowUp, ArrowDown, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import { Badge } from '../common/Badge';
import type { Opportunity } from '../../types';

interface OpportunityCardProps {
  opportunity: Opportunity;
  isSelected: boolean;
  onClick: () => void;
}

export function OpportunityCard({
  opportunity,
  isSelected,
  onClick,
}: OpportunityCardProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercent = (pct: number) => {
    return `${pct.toFixed(2)}%`;
  };

  const getTimeRemaining = () => {
    const settlement = new Date(opportunity.settlementTime);
    const now = new Date();
    const diff = settlement.getTime() - now.getTime();

    if (diff < 0) return 'Expired';

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (hours > 24) {
      const days = Math.floor(hours / 24);
      return `${days}d ${hours % 24}h`;
    }

    return `${hours}h ${minutes}m`;
  };

  const getProfitVariant = () => {
    if (opportunity.netProfitPct >= 5) return 'success';
    if (opportunity.netProfitPct >= 3) return 'warning';
    return 'default';
  };

  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-4 rounded-lg border cursor-pointer transition-all',
        isSelected
          ? 'bg-gray-700 border-emerald-500'
          : 'bg-gray-800 border-gray-700 hover:border-gray-600'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge size="sm">{opportunity.asset}</Badge>
            <span className="text-sm text-gray-400">
              {opportunity.thresholdDirection === 'above' ? (
                <ArrowUp className="w-4 h-4 inline text-emerald-500" />
              ) : (
                <ArrowDown className="w-4 h-4 inline text-red-500" />
              )}
              {formatCurrency(opportunity.thresholdStrike)}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1 truncate max-w-[200px]">
            {opportunity.thresholdTitle}
          </p>
        </div>

        <Badge variant={getProfitVariant()}>
          {formatPercent(opportunity.netProfitPct)}
        </Badge>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Spot</p>
          <p className="font-medium text-white">
            {opportunity.spotPrice
              ? formatCurrency(opportunity.spotPrice)
              : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Liquidity</p>
          <p className="font-medium text-white">
            {formatCurrency(opportunity.maxLiquidityUsd)}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Time</p>
          <p className="font-medium text-white flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {getTimeRemaining()}
          </p>
        </div>
      </div>

      {/* Divergence */}
      <div className="mt-3 pt-3 border-t border-gray-700">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">
            Threshold: {(opportunity.thresholdYesPrice * 100).toFixed(0)}c
          </span>
          <span className="text-gray-500">
            Implied: {(opportunity.impliedPrice * 100).toFixed(0)}c
          </span>
          <span
            className={clsx(
              'font-medium',
              opportunity.divergence > 0 ? 'text-red-400' : 'text-emerald-400'
            )}
          >
            {opportunity.divergence > 0 ? '+' : ''}
            {(opportunity.divergence * 100).toFixed(1)}c
          </span>
        </div>
      </div>
    </div>
  );
}
