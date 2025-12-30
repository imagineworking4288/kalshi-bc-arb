import { useTradingStore } from '../../stores/tradingStore';
import { api } from '../../services/api';

export function ModeBanner() {
  const mode = useTradingStore((s) => s.mode);
  const setBalance = useTradingStore((s) => s.setBalance);

  const handleReset = async () => {
    if (confirm('Reset paper account to $10,000?')) {
      await api.resetPaper();
      const balance = await api.getBalance();
      setBalance(balance);
    }
  };

  if (mode === 'paper') {
    return (
      <div className="p-3 bg-blue-900/50 border border-blue-600 rounded-lg flex justify-between items-center">
        <p className="text-blue-200">
          <strong>PAPER MODE</strong> - Trades are simulated. No real orders.
        </p>
        <button
          onClick={handleReset}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
        >
          Reset Account
        </button>
      </div>
    );
  }

  return (
    <div className="p-3 bg-red-900/50 border border-red-600 rounded-lg">
      <p className="text-red-200">
        <strong>LIVE MODE</strong> - Trading with REAL MONEY. Trades are irreversible.
      </p>
    </div>
  );
}
