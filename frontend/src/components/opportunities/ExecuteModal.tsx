import { useState } from 'react';
import { useTradingStore } from '../../stores/tradingStore';
import { api } from '../../services/api';
import { Modal } from '../common/Modal';
import { formatCurrency } from '../../utils/format';
import clsx from 'clsx';

export function ExecuteModal() {
  const mode = useTradingStore((s) => s.mode);
  const opportunity = useTradingStore((s) => s.selectedOpportunity);
  const balance = useTradingStore((s) => s.balance);
  const closeModal = useTradingStore((s) => s.closeExecuteModal);
  const setBalance = useTradingStore((s) => s.setBalance);

  const [numContracts, setNumContracts] = useState(10);
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<any>(null);

  if (!opportunity) return null;

  const totalCost = numContracts * opportunity.cost_per_set;
  const totalFees = numContracts * opportunity.fees_per_set;
  const totalRequired = totalCost + totalFees;
  const expectedPayout = numContracts;
  const expectedProfit = expectedPayout - totalRequired;
  const canAfford = balance ? totalRequired <= balance.available_balance : false;

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const res = await api.executeArbitrage(opportunity.id, numContracts);
      setResult(res);
      // Refresh balance
      const newBalance = await api.getBalance();
      setBalance(newBalance);
    } catch (err: any) {
      setResult({ status: 'error', message: err.message });
    }
    setExecuting(false);
  };

  return (
    <Modal onClose={closeModal}>
      <div className={clsx(
        'p-4 rounded-t-lg',
        mode === 'paper' ? 'bg-blue-600' : 'bg-red-600'
      )}>
        <h2 className="text-xl font-bold text-white">
          {mode === 'paper' ? 'Paper' : 'Live'} Arbitrage
        </h2>
      </div>

      <div className="p-4 space-y-4">
        {mode === 'live' && (
          <div className="p-3 bg-red-900/50 border border-red-600 rounded text-red-200">
            This will execute REAL trades with REAL money
          </div>
        )}

        <div>
          <h3 className="font-medium">{opportunity.threshold_title}</h3>
          <p className="text-gray-400 text-sm">
            Buy YES on {opportunity.bracket_count} brackets
          </p>
        </div>

        <div className="bg-gray-700 rounded p-3 max-h-40 overflow-y-auto">
          <div className="text-sm text-gray-400 mb-2">Positions:</div>
          {opportunity.brackets.map((b, i) => (
            <div key={i} className="flex justify-between text-sm py-1">
              <span>${b.low.toLocaleString()} - ${b.high.toLocaleString()}</span>
              <span className="text-gray-400">{(b.yes_price * 100).toFixed(0)}c</span>
            </div>
          ))}
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Contract sets:</label>
          <input
            type="number"
            min={1}
            max={opportunity.max_contracts}
            value={numContracts}
            onChange={(e) => setNumContracts(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-full p-2 bg-gray-700 rounded border border-gray-600"
          />
          <p className="text-sm text-gray-400 mt-1">Max: {opportunity.max_contracts}</p>
        </div>

        <div className="bg-gray-700 rounded p-3 space-y-2">
          <div className="flex justify-between">
            <span className="text-gray-400">Cost:</span>
            <span>{formatCurrency(totalCost)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Fees:</span>
            <span>{formatCurrency(totalFees)}</span>
          </div>
          <div className="flex justify-between font-bold border-t border-gray-600 pt-2">
            <span>Total:</span>
            <span className={!canAfford ? 'text-red-400' : ''}>{formatCurrency(totalRequired)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Payout:</span>
            <span>{formatCurrency(expectedPayout)}</span>
          </div>
          <div className="flex justify-between text-green-400">
            <span>Profit:</span>
            <span>+{formatCurrency(expectedProfit)}</span>
          </div>
        </div>

        {!canAfford && (
          <div className="text-red-400 text-sm">
            Insufficient balance. Have: {formatCurrency(balance?.available_balance || 0)}
          </div>
        )}

        {result && (
          <div className={clsx(
            'p-3 rounded',
            result.status === 'success' ? 'bg-green-900/50 text-green-200' : 'bg-red-900/50 text-red-200'
          )}>
            {result.message}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={closeModal}
            className="flex-1 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg"
          >
            {result ? 'Close' : 'Cancel'}
          </button>
          {!result && (
            <button
              onClick={handleExecute}
              disabled={!canAfford || executing}
              className={clsx(
                'flex-1 py-2 rounded-lg font-bold text-white',
                mode === 'paper' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-red-600 hover:bg-red-700',
                (!canAfford || executing) && 'opacity-50 cursor-not-allowed'
              )}
            >
              {executing ? 'Executing...' : 'Execute'}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}
