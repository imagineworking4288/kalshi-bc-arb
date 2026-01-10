/**
 * Main arbitrage prediction tab component.
 * Shows opportunities, allows execution, and displays results.
 */

import React, { useState, useMemo } from 'react';
import {
  useOpportunities,
  useExecution,
  useTradingMode,
  ArbitrageOpportunity,
  ExecutionResult,
} from './hooks/useArbitrage';

// ============ Utility Functions ============

function formatCurrency(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

// ============ Sub-components ============

interface OpportunityCardProps {
  opportunity: ArbitrageOpportunity;
  onExecute: () => void;
  executing: boolean;
}

const OpportunityCard: React.FC<OpportunityCardProps> = ({
  opportunity,
  onExecute,
  executing,
}) => {
  const [expanded, setExpanded] = useState(false);
  const profitCents = opportunity.profit_after_fees_cents || (opportunity.profit_per_set || 0) * 100;
  const profitDollars = profitCents / 100;
  const costCents = opportunity.total_cost_cents || (opportunity.cost_per_set || 0) * 100;
  const costDollars = costCents / 100;
  const roiPercent = opportunity.roi_percent || opportunity.net_profit_pct || 0;

  return (
    <div
      className={`bg-gray-800 border rounded-lg p-4 transition-all ${
        opportunity.is_stale
          ? 'opacity-60 border-yellow-500'
          : 'border-gray-700 hover:border-gray-600'
      }`}
    >
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-lg text-white">
            {opportunity.event_title || opportunity.threshold_title || opportunity.asset}
          </h3>
          <p className="text-sm text-gray-400">
            {opportunity.event_ticker || opportunity.id}
          </p>
          {opportunity.settlement_time && (
            <p className="text-xs text-gray-500 mt-1">
              Settlement: {new Date(opportunity.settlement_time).toLocaleString()}
            </p>
          )}
        </div>
        <div className="text-right">
          <div
            className={`text-xl font-bold ${
              profitDollars > 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {profitDollars > 0 ? '+' : ''}{formatCurrency(profitCents)}
          </div>
          <div className="text-sm text-gray-400">{formatPercent(roiPercent)} ROI</div>
        </div>
      </div>

      {/* Strategy & Info Badges */}
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="px-2 py-1 bg-blue-900/50 text-blue-300 text-xs rounded">
          {(opportunity.strategy || 'ALL YES').replace('_', ' ').toUpperCase()}
        </span>
        {opportunity.bracket_count && (
          <span className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded">
            {opportunity.bracket_count} brackets
          </span>
        )}
        {opportunity.max_contracts && (
          <span className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded">
            Max: {opportunity.max_contracts} contracts
          </span>
        )}
        {opportunity.spot_price && (
          <span className="px-2 py-1 bg-purple-900/50 text-purple-300 text-xs rounded">
            Spot: ${opportunity.spot_price.toLocaleString()}
          </span>
        )}
      </div>

      {/* Expandable Legs Table */}
      {((opportunity.legs?.length ?? 0) > 0 || (opportunity.brackets?.length ?? 0) > 0) && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-blue-400 hover:text-blue-300 mb-2"
          >
            {expanded ? '- Hide details' : '+ Show details'}
          </button>

          {expanded && (
            <div className="mb-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left py-1 text-gray-400">Bracket</th>
                    <th className="text-left py-1 text-gray-400">Range</th>
                    <th className="text-right py-1 text-gray-400">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {(opportunity.legs || []).map((leg, i) => (
                    <tr key={i} className="border-b border-gray-800">
                      <td className="py-1 text-gray-300">{leg.ticker}</td>
                      <td className="py-1 text-gray-400">{leg.bracket_label}</td>
                      <td className="text-right py-1 text-green-400">
                        {leg.price_cents}¢
                      </td>
                    </tr>
                  ))}
                  {(opportunity.brackets || []).map((b, i) => (
                    <tr key={i} className="border-b border-gray-800">
                      <td className="py-1 text-gray-300">{b.ticker}</td>
                      <td className="py-1 text-gray-400">
                        ${b.low.toLocaleString()} - ${b.high.toLocaleString()}
                      </td>
                      <td className="text-right py-1 text-green-400">
                        {Math.round(b.yes_price * 100)}¢
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="font-semibold">
                    <td colSpan={2} className="py-1 text-gray-300">Total Cost</td>
                    <td className="text-right py-1 text-white">
                      ${costDollars.toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </>
      )}

      {/* Warnings */}
      {opportunity.warnings && opportunity.warnings.length > 0 && (
        <div className="mb-3 text-sm text-yellow-400 bg-yellow-900/20 p-2 rounded">
          {opportunity.warnings.map((w, i) => (
            <div key={i}>Warning: {w}</div>
          ))}
        </div>
      )}

      {/* Stale Warning */}
      {opportunity.is_stale && (
        <div className="mb-3 text-sm text-yellow-400 bg-yellow-900/20 p-2 rounded">
          Data may be stale - refresh before executing
        </div>
      )}

      {/* Execute Button */}
      <button
        onClick={onExecute}
        disabled={executing || opportunity.is_stale}
        className={`w-full py-2 px-4 rounded font-semibold transition-colors ${
          executing || opportunity.is_stale
            ? 'bg-gray-600 cursor-not-allowed text-gray-400'
            : 'bg-blue-600 hover:bg-blue-700 text-white'
        }`}
      >
        {executing ? 'Executing...' : `Execute (+${formatCurrency(profitCents)} profit)`}
      </button>
    </div>
  );
};

interface ExecutionResultBannerProps {
  result: ExecutionResult;
  onDismiss: () => void;
}

const ExecutionResultBanner: React.FC<ExecutionResultBannerProps> = ({
  result,
  onDismiss,
}) => {
  return (
    <div
      className={`p-4 rounded-lg flex justify-between items-start ${
        result.success
          ? 'bg-green-900/50 border border-green-700'
          : 'bg-red-900/50 border border-red-700'
      }`}
    >
      <div>
        <div className="font-semibold text-lg">
          {result.success ? 'Execution Successful' : 'Execution Failed'}
        </div>
        <div className="text-sm text-gray-300">
          {result.success
            ? `Profit: ${formatCurrency(result.profit_cents || (result.expected_profit || 0) * 100)} (${result.trading_mode})`
            : result.errors?.join(', ') || result.message || 'Unknown error'}
        </div>
        {result.orders && result.orders.length > 0 && (
          <div className="text-xs text-gray-400 mt-1">
            {result.orders.length} orders filled
          </div>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="text-gray-400 hover:text-white"
      >
        Dismiss
      </button>
    </div>
  );
};

interface ConfirmationModalProps {
  opportunity: ArbitrageOpportunity;
  tradingMode: string;
  onConfirm: () => void;
  onCancel: () => void;
  executing: boolean;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  opportunity,
  tradingMode,
  onConfirm,
  onCancel,
  executing,
}) => {
  const profitCents = opportunity.profit_after_fees_cents || (opportunity.profit_per_set || 0) * 100;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 max-w-md mx-4">
        <h3 className={`text-xl font-bold mb-4 ${tradingMode === 'live' ? 'text-red-400' : 'text-yellow-400'}`}>
          {tradingMode === 'live' ? 'Live Trading Confirmation' : 'Paper Trading Confirmation'}
        </h3>

        {tradingMode === 'live' && (
          <p className="mb-4 text-red-300">
            You are about to execute a LIVE trade. This will use real money.
          </p>
        )}

        <div className="mb-4 p-3 bg-gray-700 rounded">
          <div className="text-sm text-gray-400">Opportunity</div>
          <div className="font-semibold text-white">
            {opportunity.event_title || opportunity.threshold_title}
          </div>
          <div className="text-green-400 font-bold mt-2">
            Expected Profit: {formatCurrency(profitCents)}
          </div>
        </div>

        <div className="flex gap-4">
          <button
            onClick={onCancel}
            disabled={executing}
            className="flex-1 py-2 px-4 bg-gray-600 hover:bg-gray-500 rounded text-white"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={executing}
            className={`flex-1 py-2 px-4 rounded text-white font-semibold ${
              tradingMode === 'live'
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {executing ? 'Executing...' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ============ Main Component ============

export const PredictionTab: React.FC = () => {
  const {
    opportunities,
    loading,
    error,
    lastUpdated,
    tradingMode,
    refresh,
  } = useOpportunities(1.0);

  const { execute, executing, lastResult, clearResult } = useExecution();
  const { mode } = useTradingMode();

  const [selectedOpp, setSelectedOpp] = useState<ArbitrageOpportunity | null>(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [minProfit, setMinProfit] = useState(0);

  // Filter opportunities by minimum profit
  const filteredOpportunities = useMemo(() => {
    return opportunities.filter(opp => {
      const profit = opp.profit_after_fees_cents || (opp.profit_per_set || 0) * 100;
      return profit >= minProfit;
    });
  }, [opportunities, minProfit]);

  const handleExecute = (opportunity: ArbitrageOpportunity) => {
    setSelectedOpp(opportunity);
    setShowConfirmation(true);
  };

  const confirmExecution = async () => {
    if (!selectedOpp) return;

    try {
      await execute(selectedOpp.id || selectedOpp.event_ticker, 1, mode === 'live');
    } finally {
      setShowConfirmation(false);
      setSelectedOpp(null);
    }
  };

  const cancelExecution = () => {
    setShowConfirmation(false);
    setSelectedOpp(null);
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white">Arbitrage Opportunities</h2>
          <p className="text-sm text-gray-400">
            Last updated: {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : 'Never'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span
            className={`px-3 py-1 rounded text-sm font-semibold ${
              tradingMode === 'paper' || mode === 'paper'
                ? 'bg-yellow-900/50 text-yellow-300'
                : 'bg-red-900/50 text-red-300'
            }`}
          >
            {(tradingMode || mode).toUpperCase()} MODE
          </span>
          <button
            onClick={refresh}
            disabled={loading}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 p-3 bg-gray-800 rounded-lg">
        <label className="text-sm text-gray-400">Min Profit:</label>
        <input
          type="range"
          min="0"
          max="100"
          value={minProfit}
          onChange={(e) => setMinProfit(Number(e.target.value))}
          className="w-32"
        />
        <span className="text-sm text-white">{formatCurrency(minProfit)}</span>
        <span className="text-sm text-gray-400 ml-4">
          Showing {filteredOpportunities.length} of {opportunities.length}
        </span>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">
          {error}
        </div>
      )}

      {/* Last Execution Result */}
      {lastResult && (
        <ExecutionResultBanner result={lastResult} onDismiss={clearResult} />
      )}

      {/* Opportunities Grid */}
      {loading && opportunities.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <div className="animate-pulse">Loading opportunities...</div>
        </div>
      ) : filteredOpportunities.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <div className="text-lg mb-2">No profitable opportunities found</div>
          <div className="text-sm">
            Markets are efficiently priced. Keep watching for inefficiencies.
          </div>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredOpportunities.map((opp) => (
            <OpportunityCard
              key={opp.id || opp.event_ticker}
              opportunity={opp}
              onExecute={() => handleExecute(opp)}
              executing={executing}
            />
          ))}
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmation && selectedOpp && (
        <ConfirmationModal
          opportunity={selectedOpp}
          tradingMode={tradingMode || mode}
          onConfirm={confirmExecution}
          onCancel={cancelExecution}
          executing={executing}
        />
      )}
    </div>
  );
};

export default PredictionTab;
