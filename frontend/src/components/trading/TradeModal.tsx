import { useState, useEffect } from 'react';
import { AlertCircle, Check, X } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { useTradeStore } from '../../stores/tradeStore';
import { useOpportunityStore } from '../../stores/opportunityStore';
import { api } from '../../services/api';

export function TradeModal() {
  const {
    tradeModalOpen,
    selectedOpportunityId,
    positionSize,
    sizingSuggestions,
    tradeDetails,
    isTrading,
    lastTradeResult,
    error,
    closeTradeModal,
    setPositionSize,
    setSizingSuggestions,
    setTradeDetails,
    setTrading,
    setTradeResult,
    setError,
  } = useTradeStore();

  const { opportunities, balance } = useOpportunityStore();
  const [step, setStep] = useState<'size' | 'confirm' | 'result'>('size');

  const opportunity = opportunities.find((o) => o.id === selectedOpportunityId);

  // Load suggestions when modal opens
  useEffect(() => {
    if (tradeModalOpen && selectedOpportunityId) {
      loadSuggestions();
    }
  }, [tradeModalOpen, selectedOpportunityId]);

  // Update trade details when position size changes
  useEffect(() => {
    if (positionSize > 0 && selectedOpportunityId) {
      updateTradeDetails();
    }
  }, [positionSize, selectedOpportunityId]);

  const loadSuggestions = async () => {
    if (!selectedOpportunityId) return;
    try {
      const data = await api.getTradeSuggestions(selectedOpportunityId);
      setSizingSuggestions(data.suggestions);
    } catch (err) {
      console.error('Failed to load suggestions', err);
    }
  };

  const updateTradeDetails = async () => {
    if (!selectedOpportunityId || positionSize <= 0) return;
    try {
      const data = await api.getTradeSuggestions(selectedOpportunityId, positionSize);
      setTradeDetails(data.tradeDetails);
    } catch (err) {
      console.error('Failed to update trade details', err);
    }
  };

  const handleSuggestionClick = (amount: number) => {
    setPositionSize(amount);
  };

  const handleConfirm = () => {
    setStep('confirm');
  };

  const handleExecute = async () => {
    if (!selectedOpportunityId) return;

    setTrading(true);
    setError(null);

    try {
      const data = await api.executeTrade(selectedOpportunityId, positionSize);
      setTradeResult(data.result);
      setStep('result');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade failed');
    }
  };

  const handleClose = () => {
    setStep('size');
    closeTradeModal();
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  if (!opportunity) return null;

  return (
    <Modal
      isOpen={tradeModalOpen}
      onClose={handleClose}
      title={step === 'result' ? 'Trade Result' : 'Execute Trade'}
      size="md"
    >
      {step === 'size' && (
        <div className="space-y-6">
          {/* Opportunity summary */}
          <div className="bg-gray-700/50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">{opportunity.asset}</span>
              <span className="text-emerald-400 font-medium">
                {opportunity.netProfitPct.toFixed(2)}% net
              </span>
            </div>
            <p className="text-white font-medium">{opportunity.thresholdTitle}</p>
          </div>

          {/* Position size input */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Position Size (USD)
            </label>
            <input
              type="number"
              value={positionSize || ''}
              onChange={(e) => setPositionSize(parseFloat(e.target.value) || 0)}
              placeholder="Enter amount..."
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500"
            />
            {balance && (
              <p className="text-xs text-gray-500 mt-1">
                Available: {formatCurrency(balance.availableBalance)}
              </p>
            )}
          </div>

          {/* Sizing suggestions */}
          {sizingSuggestions && (
            <div>
              <p className="text-sm font-medium text-gray-400 mb-2">
                Suggested Sizes
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => handleSuggestionClick(sizingSuggestions.conservative)}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-sm rounded-lg text-gray-300"
                >
                  Conservative ({formatCurrency(sizingSuggestions.conservative)})
                </button>
                <button
                  onClick={() => handleSuggestionClick(sizingSuggestions.moderate)}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-sm rounded-lg text-gray-300"
                >
                  Moderate ({formatCurrency(sizingSuggestions.moderate)})
                </button>
                <button
                  onClick={() => handleSuggestionClick(sizingSuggestions.aggressive)}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-sm rounded-lg text-gray-300"
                >
                  Aggressive ({formatCurrency(sizingSuggestions.aggressive)})
                </button>
              </div>
            </div>
          )}

          {/* Trade details preview */}
          {tradeDetails && (
            <div className="bg-gray-700/50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Contracts</span>
                <span className="text-white">{tradeDetails.contracts}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Total Cost</span>
                <span className="text-white">
                  {formatCurrency(tradeDetails.totalCost)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Fees</span>
                <span className="text-white">
                  {formatCurrency(tradeDetails.totalFees)}
                </span>
              </div>
              <div className="flex justify-between text-sm border-t border-gray-600 pt-2">
                <span className="text-gray-400">Expected Profit</span>
                <span className="text-emerald-400 font-medium">
                  {formatCurrency(tradeDetails.netProfit)} (
                  {tradeDetails.netProfitPct.toFixed(2)}%)
                </span>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button variant="secondary" onClick={handleClose} className="flex-1">
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={!positionSize || positionSize <= 0}
              className="flex-1"
            >
              Continue
            </Button>
          </div>
        </div>
      )}

      {step === 'confirm' && (
        <div className="space-y-6">
          <div className="p-4 bg-yellow-900/20 border border-yellow-700 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-yellow-400 font-medium">Confirm Trade</p>
                <p className="text-sm text-gray-400 mt-1">
                  You are about to execute a trade for{' '}
                  {formatCurrency(positionSize)}. This action cannot be undone.
                </p>
              </div>
            </div>
          </div>

          {tradeDetails && (
            <div className="bg-gray-700/50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-400">Investment</span>
                <span className="text-white font-medium">
                  {formatCurrency(tradeDetails.totalInvestment)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Guaranteed Payout</span>
                <span className="text-white font-medium">
                  {formatCurrency(tradeDetails.guaranteedPayout)}
                </span>
              </div>
              <div className="flex justify-between border-t border-gray-600 pt-2">
                <span className="text-gray-400">Net Profit</span>
                <span className="text-emerald-400 font-medium">
                  {formatCurrency(tradeDetails.netProfit)}
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-900/20 border border-red-700 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={() => setStep('size')}
              disabled={isTrading}
              className="flex-1"
            >
              Back
            </Button>
            <Button onClick={handleExecute} loading={isTrading} className="flex-1">
              Execute Trade
            </Button>
          </div>
        </div>
      )}

      {step === 'result' && lastTradeResult && (
        <div className="space-y-6">
          <div
            className={`p-4 rounded-lg ${
              lastTradeResult.status === 'success'
                ? 'bg-emerald-900/20 border border-emerald-700'
                : lastTradeResult.status === 'partial'
                ? 'bg-yellow-900/20 border border-yellow-700'
                : 'bg-red-900/20 border border-red-700'
            }`}
          >
            <div className="flex items-center gap-3">
              {lastTradeResult.status === 'success' ? (
                <Check className="w-6 h-6 text-emerald-400" />
              ) : lastTradeResult.status === 'partial' ? (
                <AlertCircle className="w-6 h-6 text-yellow-400" />
              ) : (
                <X className="w-6 h-6 text-red-400" />
              )}
              <div>
                <p
                  className={`font-medium ${
                    lastTradeResult.status === 'success'
                      ? 'text-emerald-400'
                      : lastTradeResult.status === 'partial'
                      ? 'text-yellow-400'
                      : 'text-red-400'
                  }`}
                >
                  {lastTradeResult.status === 'success'
                    ? 'Trade Successful'
                    : lastTradeResult.status === 'partial'
                    ? 'Partially Filled'
                    : 'Trade Failed'}
                </p>
                <p className="text-sm text-gray-400">{lastTradeResult.message}</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-700/50 rounded-lg p-4 space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400">Total Cost</span>
              <span className="text-white">
                {formatCurrency(lastTradeResult.totalCost)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Fees Paid</span>
              <span className="text-white">
                {formatCurrency(lastTradeResult.totalFees)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Expected Payout</span>
              <span className="text-white">
                {formatCurrency(lastTradeResult.expectedPayout)}
              </span>
            </div>
            <div className="flex justify-between border-t border-gray-600 pt-2">
              <span className="text-gray-400">Expected Profit</span>
              <span className="text-emerald-400 font-medium">
                {formatCurrency(lastTradeResult.expectedProfit)}
              </span>
            </div>
          </div>

          {/* Order details */}
          <div>
            <p className="text-sm font-medium text-gray-400 mb-2">Order Details</p>
            <div className="space-y-2">
              {lastTradeResult.orders.map((order, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 bg-gray-700/50 rounded"
                >
                  <span className="text-sm text-gray-300 truncate flex-1">
                    {order.ticker}
                  </span>
                  <span
                    className={`text-sm ${
                      order.status === 'filled'
                        ? 'text-emerald-400'
                        : order.status === 'partial'
                        ? 'text-yellow-400'
                        : 'text-red-400'
                    }`}
                  >
                    {order.filled}/{order.requested}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <Button onClick={handleClose} className="w-full">
            Close
          </Button>
        </div>
      )}
    </Modal>
  );
}
