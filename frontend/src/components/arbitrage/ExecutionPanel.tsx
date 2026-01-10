/**
 * Order execution interface component.
 * Allows users to configure and execute trades with live feedback.
 */

import React, { useState, useEffect } from 'react';
import {
  useExecution,
  useTradingMode,
  useOpportunities,
  ArbitrageOpportunity,
  ExecutionResult,
} from './hooks/useArbitrage';

// ============ Utility Functions ============

function formatCurrency(cents: number): string {
  const dollars = cents / 100;
  return dollars >= 0 ? `$${dollars.toFixed(2)}` : `-$${Math.abs(dollars).toFixed(2)}`;
}

// ============ Sub-components ============

interface OpportunitySelectorProps {
  opportunities: ArbitrageOpportunity[];
  selected: ArbitrageOpportunity | null;
  onSelect: (opp: ArbitrageOpportunity | null) => void;
}

const OpportunitySelector: React.FC<OpportunitySelectorProps> = ({
  opportunities,
  selected,
  onSelect,
}) => {
  return (
    <div className="space-y-2">
      <label className="block text-sm text-gray-400">Select Opportunity</label>
      <select
        value={selected?.id || ''}
        onChange={(e) => {
          const opp = opportunities.find((o) => o.id === e.target.value);
          onSelect(opp || null);
        }}
        className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
      >
        <option value="">-- Select an opportunity --</option>
        {opportunities.map((opp) => (
          <option key={opp.id} value={opp.id}>
            {opp.event_title || opp.threshold_title || opp.asset} -{' '}
            {formatCurrency(
              opp.profit_after_fees_cents || (opp.profit_per_set || 0) * 100
            )}{' '}
            profit
          </option>
        ))}
      </select>
    </div>
  );
};

interface ExecutionConfigProps {
  numContracts: number;
  onNumContractsChange: (n: number) => void;
  maxSlippage: number;
  onMaxSlippageChange: (n: number) => void;
  confirmLive: boolean;
  onConfirmLiveChange: (v: boolean) => void;
  tradingMode: string;
}

const ExecutionConfig: React.FC<ExecutionConfigProps> = ({
  numContracts,
  onNumContractsChange,
  maxSlippage,
  onMaxSlippageChange,
  confirmLive,
  onConfirmLiveChange,
  tradingMode,
}) => {
  return (
    <div className="space-y-4">
      {/* Number of Contracts */}
      <div>
        <label className="block text-sm text-gray-400 mb-1">
          Number of Contracts
        </label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min="1"
            max="100"
            value={numContracts}
            onChange={(e) => onNumContractsChange(Number(e.target.value))}
            className="flex-1"
          />
          <input
            type="number"
            min="1"
            max="100"
            value={numContracts}
            onChange={(e) =>
              onNumContractsChange(Math.max(1, Math.min(100, Number(e.target.value))))
            }
            className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-center"
          />
        </div>
      </div>

      {/* Max Slippage */}
      <div>
        <label className="block text-sm text-gray-400 mb-1">
          Max Slippage (cents)
        </label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min="0"
            max="10"
            value={maxSlippage}
            onChange={(e) => onMaxSlippageChange(Number(e.target.value))}
            className="flex-1"
          />
          <span className="w-16 text-center text-white">{maxSlippage}¢</span>
        </div>
      </div>

      {/* Live Trading Confirmation */}
      {tradingMode === 'live' && (
        <div className="p-3 bg-red-900/30 border border-red-700 rounded">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={confirmLive}
              onChange={(e) => onConfirmLiveChange(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-red-300 text-sm">
              I confirm this is a LIVE trade with real money
            </span>
          </label>
        </div>
      )}
    </div>
  );
};

interface OrderPreviewProps {
  opportunity: ArbitrageOpportunity;
  numContracts: number;
}

const OrderPreview: React.FC<OrderPreviewProps> = ({ opportunity, numContracts }) => {
  const profitPerSet =
    opportunity.profit_after_fees_cents || (opportunity.profit_per_set || 0) * 100;
  const costPerSet =
    opportunity.total_cost_cents || (opportunity.cost_per_set || 0) * 100;
  const feesPerSet =
    opportunity.total_fees_cents || (opportunity.fees_per_set || 0) * 100;

  const totalCost = costPerSet * numContracts;
  const totalFees = feesPerSet * numContracts;
  const totalProfit = profitPerSet * numContracts;
  const payout = numContracts * 100; // $1 per contract set

  return (
    <div className="bg-gray-700 rounded p-4 space-y-3">
      <h4 className="font-semibold text-white">Order Preview</h4>

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="text-gray-400">Contracts per leg:</div>
        <div className="text-white text-right">{numContracts}</div>

        <div className="text-gray-400">Total legs:</div>
        <div className="text-white text-right">
          {opportunity.brackets?.length || opportunity.legs?.length || 0}
        </div>

        <div className="text-gray-400">Cost:</div>
        <div className="text-white text-right">{formatCurrency(totalCost)}</div>

        <div className="text-gray-400">Fees:</div>
        <div className="text-white text-right">{formatCurrency(totalFees)}</div>

        <div className="text-gray-400">Total investment:</div>
        <div className="text-white text-right font-semibold">
          {formatCurrency(totalCost + totalFees)}
        </div>

        <div className="border-t border-gray-600 col-span-2 my-1"></div>

        <div className="text-gray-400">Expected payout:</div>
        <div className="text-white text-right">{formatCurrency(payout)}</div>

        <div className="text-gray-400">Expected profit:</div>
        <div className="text-green-400 text-right font-bold">
          {formatCurrency(totalProfit)}
        </div>
      </div>
    </div>
  );
};

interface ExecutionHistoryItemProps {
  result: ExecutionResult;
}

const ExecutionHistoryItem: React.FC<ExecutionHistoryItemProps> = ({ result }) => {
  return (
    <div
      className={`p-3 rounded border ${
        result.success
          ? 'bg-green-900/20 border-green-700'
          : 'bg-red-900/20 border-red-700'
      }`}
    >
      <div className="flex justify-between items-center">
        <div>
          <span
            className={`font-semibold ${
              result.success ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {result.success ? 'Success' : 'Failed'}
          </span>
          <span className="text-gray-400 text-sm ml-2">
            ID: {result.execution_id || result.trade_id}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {result.trading_mode?.toUpperCase()}
        </span>
      </div>
      {result.success && result.profit_cents && (
        <div className="text-sm text-green-400 mt-1">
          Profit: {formatCurrency(result.profit_cents)}
        </div>
      )}
      {!result.success && result.errors?.length > 0 && (
        <div className="text-sm text-red-400 mt-1">{result.errors.join(', ')}</div>
      )}
    </div>
  );
};

// ============ Main Component ============

export const ExecutionPanel: React.FC = () => {
  const { opportunities, refresh: refreshOpportunities } = useOpportunities(0);
  const { execute, executing, lastResult, error, clearResult } = useExecution();
  const { mode } = useTradingMode();

  const [selectedOpp, setSelectedOpp] = useState<ArbitrageOpportunity | null>(null);
  const [numContracts, setNumContracts] = useState(1);
  const [maxSlippage, setMaxSlippage] = useState(3);
  const [confirmLive, setConfirmLive] = useState(false);
  const [history, setHistory] = useState<ExecutionResult[]>([]);

  // Add to history when execution completes
  useEffect(() => {
    if (lastResult) {
      setHistory((prev) => [lastResult, ...prev.slice(0, 9)]);
    }
  }, [lastResult]);

  const handleExecute = async () => {
    if (!selectedOpp) return;

    if (mode === 'live' && !confirmLive) {
      return;
    }

    try {
      await execute(selectedOpp.id || selectedOpp.event_ticker, numContracts, confirmLive);
      // Reset confirmation after execution
      setConfirmLive(false);
    } catch (err) {
      // Error is handled by the hook
    }
  };

  const canExecute =
    selectedOpp && !executing && (mode === 'paper' || confirmLive);

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-white">Execution Panel</h2>
        <span
          className={`px-3 py-1 rounded text-sm font-semibold ${
            mode === 'paper'
              ? 'bg-yellow-900/50 text-yellow-300'
              : 'bg-red-900/50 text-red-300'
          }`}
        >
          {mode.toUpperCase()} MODE
        </span>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Left Column: Configuration */}
        <div className="space-y-6">
          {/* Opportunity Selection */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="font-semibold text-lg text-white mb-4">
              Select Opportunity
            </h3>
            <OpportunitySelector
              opportunities={opportunities}
              selected={selectedOpp}
              onSelect={setSelectedOpp}
            />
            <button
              onClick={refreshOpportunities}
              className="mt-3 text-sm text-blue-400 hover:text-blue-300"
            >
              Refresh opportunities
            </button>
          </div>

          {/* Execution Configuration */}
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="font-semibold text-lg text-white mb-4">
              Configuration
            </h3>
            <ExecutionConfig
              numContracts={numContracts}
              onNumContractsChange={setNumContracts}
              maxSlippage={maxSlippage}
              onMaxSlippageChange={setMaxSlippage}
              confirmLive={confirmLive}
              onConfirmLiveChange={setConfirmLive}
              tradingMode={mode}
            />
          </div>
        </div>

        {/* Right Column: Preview & Execute */}
        <div className="space-y-6">
          {/* Order Preview */}
          {selectedOpp && (
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="font-semibold text-lg text-white mb-4">
                Order Preview
              </h3>
              <OrderPreview opportunity={selectedOpp} numContracts={numContracts} />
            </div>
          )}

          {/* Execute Button */}
          <button
            onClick={handleExecute}
            disabled={!canExecute}
            className={`w-full py-4 rounded-lg font-bold text-lg transition-colors ${
              canExecute
                ? mode === 'live'
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-gray-600 text-gray-400 cursor-not-allowed'
            }`}
          >
            {executing
              ? 'Executing...'
              : !selectedOpp
              ? 'Select an Opportunity'
              : mode === 'live' && !confirmLive
              ? 'Confirm Live Trading First'
              : `Execute ${mode === 'live' ? 'LIVE' : 'Paper'} Trade`}
          </button>

          {/* Error Display */}
          {error && (
            <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">
              {error}
            </div>
          )}

          {/* Last Result */}
          {lastResult && (
            <div
              className={`p-4 rounded-lg ${
                lastResult.success
                  ? 'bg-green-900/30 border border-green-700'
                  : 'bg-red-900/30 border border-red-700'
              }`}
            >
              <div className="flex justify-between items-center mb-2">
                <span
                  className={`font-bold ${
                    lastResult.success ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {lastResult.success ? 'Execution Successful!' : 'Execution Failed'}
                </span>
                <button
                  onClick={clearResult}
                  className="text-gray-400 hover:text-white text-sm"
                >
                  Dismiss
                </button>
              </div>
              {lastResult.success && (
                <div className="text-green-300">
                  Profit: {formatCurrency(lastResult.profit_cents || 0)}
                </div>
              )}
              {!lastResult.success && lastResult.errors?.length > 0 && (
                <div className="text-red-300">{lastResult.errors.join(', ')}</div>
              )}
              {lastResult.message && (
                <div className="text-gray-400 text-sm mt-1">{lastResult.message}</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Execution History */}
      {history.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h3 className="font-semibold text-lg text-white mb-4">
            Recent Executions
          </h3>
          <div className="space-y-2">
            {history.map((result, i) => (
              <ExecutionHistoryItem
                key={result.execution_id || result.trade_id || i}
                result={result}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ExecutionPanel;
