import { useState } from 'react';
import { useTradingStore } from '../../stores/tradingStore';
import { Modal } from '../common/Modal';
import clsx from 'clsx';

export function ModeToggle() {
  const mode = useTradingStore((s) => s.mode);
  const setMode = useTradingStore((s) => s.setMode);
  const [showConfirm, setShowConfirm] = useState(false);
  const [typed, setTyped] = useState('');

  const handleModeChange = (newMode: 'paper' | 'live') => {
    if (newMode === 'live' && mode === 'paper') {
      setShowConfirm(true);
    } else {
      setMode(newMode);
    }
  };

  const confirmLive = () => {
    if (typed === 'LIVE') {
      setMode('live');
      setShowConfirm(false);
      setTyped('');
    }
  };

  return (
    <>
      <div className="flex items-center gap-2 p-3 bg-gray-800 rounded-lg">
        <span className="text-sm text-gray-400">Mode:</span>
        <button
          onClick={() => handleModeChange('paper')}
          className={clsx(
            'px-4 py-2 rounded-lg font-medium transition-colors',
            mode === 'paper' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-400'
          )}
        >
          Paper
        </button>
        <button
          onClick={() => handleModeChange('live')}
          className={clsx(
            'px-4 py-2 rounded-lg font-medium transition-colors',
            mode === 'live' ? 'bg-red-600 text-white' : 'bg-gray-700 text-gray-400'
          )}
        >
          Live
        </button>
      </div>

      {showConfirm && (
        <Modal onClose={() => { setShowConfirm(false); setTyped(''); }}>
          <div className="p-6">
            <h2 className="text-xl font-bold text-red-400 mb-4">Enable Live Trading?</h2>
            <ul className="text-gray-300 space-y-2 mb-4">
              <li>- Orders will be sent to Kalshi</li>
              <li>- Real money will be used</li>
              <li>- Trades cannot be undone</li>
            </ul>
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Type "LIVE" to confirm:</label>
              <input
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value.toUpperCase())}
                className="w-full p-2 bg-gray-700 rounded border border-gray-600"
                autoFocus
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => { setShowConfirm(false); setTyped(''); }}
                className="flex-1 py-2 bg-gray-600 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={confirmLive}
                disabled={typed !== 'LIVE'}
                className={clsx(
                  'flex-1 py-2 rounded-lg font-medium',
                  typed === 'LIVE' ? 'bg-red-600 hover:bg-red-700' : 'bg-gray-700 text-gray-500 cursor-not-allowed'
                )}
              >
                Enable Live
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
