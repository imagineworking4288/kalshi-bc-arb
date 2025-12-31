import { useEffect, useState } from 'react';
import { api } from '../../services/api';

interface WatchlistItem {
  id: string;
  ticker: string;
  title: string;
  subtitle: string;
  notes: string | null;
  added_at: string;
  yes_ask: number | null;
  no_ask: number | null;
  status: string;
}

export function WatchlistTab() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addTicker, setAddTicker] = useState('');
  const [addNotes, setAddNotes] = useState('');
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadWatchlist();
  }, []);

  const loadWatchlist = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getWatchlist();
      setItems(data.items);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!addTicker.trim()) {
      setMessage({ type: 'error', text: 'Ticker is required' });
      return;
    }

    setAdding(true);
    setMessage(null);
    try {
      const result = await api.addToWatchlist(addTicker.trim().toUpperCase(), addNotes.trim() || undefined);

      if (result.already_existed) {
        setMessage({ type: 'success', text: `${result.ticker} was already in watchlist` });
      } else {
        setMessage({ type: 'success', text: `Added ${result.ticker} to watchlist` });
      }

      setAddTicker('');
      setAddNotes('');
      await loadWatchlist();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (ticker: string) => {
    if (!confirm(`Remove ${ticker} from watchlist?`)) {
      return;
    }

    try {
      await api.removeFromWatchlist(ticker);
      setMessage({ type: 'success', text: `Removed ${ticker} from watchlist` });
      await loadWatchlist();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading watchlist...</div>;
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500 rounded-lg p-4">
        <p className="text-red-400">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Add to Watchlist Form */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Add to Watchlist</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="text"
            placeholder="Ticker (e.g., KXBTC-25DEC3117-T99250)"
            value={addTicker}
            onChange={(e) => setAddTicker(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white placeholder-gray-400"
          />

          <input
            type="text"
            placeholder="Notes (optional)"
            value={addNotes}
            onChange={(e) => setAddNotes(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white placeholder-gray-400"
          />

          <button
            onClick={handleAdd}
            disabled={adding}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium rounded px-6 py-2 transition-colors"
          >
            {adding ? 'Adding...' : 'Add Market'}
          </button>
        </div>

        {message && (
          <div className={`mt-4 p-3 rounded ${
            message.type === 'success'
              ? 'bg-green-900/20 border border-green-500 text-green-400'
              : 'bg-red-900/20 border border-red-500 text-red-400'
          }`}>
            {message.text}
          </div>
        )}
      </div>

      {/* Watchlist Items */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Saved Markets ({items.length})</h2>

        {items.length === 0 ? (
          <p className="text-gray-400 text-center py-8">
            No markets in watchlist yet. Add some above to get started.
          </p>
        ) : (
          <div className="space-y-4">
            {items.map((item) => (
              <div
                key={item.id}
                className="bg-gray-700/50 rounded-lg p-4 border border-gray-600 hover:border-gray-500 transition-colors"
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="font-mono text-sm text-blue-400">{item.ticker}</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        item.status === 'open'
                          ? 'bg-green-900/30 text-green-400'
                          : 'bg-gray-600 text-gray-400'
                      }`}>
                        {item.status}
                      </span>
                    </div>

                    <h3 className="font-medium text-white">{item.title}</h3>

                    {item.subtitle && (
                      <p className="text-sm text-gray-400 mt-1">{item.subtitle}</p>
                    )}

                    {item.notes && (
                      <p className="text-sm text-gray-300 mt-2 italic">
                        Note: {item.notes}
                      </p>
                    )}
                  </div>

                  <button
                    onClick={() => handleRemove(item.ticker)}
                    className="text-red-400 hover:text-red-300 text-sm ml-4"
                  >
                    Remove
                  </button>
                </div>

                <div className="flex gap-6 mt-3 pt-3 border-t border-gray-600">
                  <div>
                    <div className="text-xs text-gray-400">YES Ask</div>
                    <div className="text-lg font-bold text-green-400">
                      {item.yes_ask !== null ? `${item.yes_ask}¢` : 'N/A'}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-gray-400">NO Ask</div>
                    <div className="text-lg font-bold text-red-400">
                      {item.no_ask !== null ? `${item.no_ask}¢` : 'N/A'}
                    </div>
                  </div>

                  <div className="ml-auto text-right">
                    <div className="text-xs text-gray-400">Added</div>
                    <div className="text-sm text-gray-300">
                      {new Date(item.added_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
