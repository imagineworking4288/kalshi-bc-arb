interface ConfigPanelProps {
  minEdge: number;
  budgetDollars: number;
  mode: 'paper' | 'live';
  autoTrade: boolean;
  onMinEdgeChange: (value: number) => void;
  onBudgetChange: (value: number) => void;
  onModeChange: (mode: 'paper' | 'live') => void;
  onAutoTradeToggle: (enabled: boolean) => void;
  extraInfo?: string;
}

export function ConfigPanel({
  minEdge,
  budgetDollars,
  mode,
  autoTrade,
  onMinEdgeChange,
  onBudgetChange,
  onModeChange,
  onAutoTradeToggle,
  extraInfo
}: ConfigPanelProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-3">
      <div className="grid grid-cols-5 gap-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Min Edge %</label>
          <input
            type="number"
            value={minEdge}
            onChange={(e) => onMinEdgeChange(parseFloat(e.target.value) || 0)}
            className="w-full bg-slate-700 text-white rounded px-2 py-1 text-sm border border-slate-600"
            step="0.5"
            min="0"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Budget ($)</label>
          <input
            type="number"
            value={budgetDollars}
            onChange={(e) => onBudgetChange(parseInt(e.target.value) || 0)}
            className="w-full bg-slate-700 text-white rounded px-2 py-1 text-sm border border-slate-600"
            step="10"
            min="1"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Mode</label>
          <select
            value={mode}
            onChange={(e) => onModeChange(e.target.value as 'paper' | 'live')}
            className="w-full bg-slate-700 text-white rounded px-2 py-1 text-sm border border-slate-600"
          >
            <option value="paper">Paper</option>
            <option value="live">Live</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Auto-Trade</label>
          <button
            onClick={() => onAutoTradeToggle(!autoTrade)}
            className={`w-full py-1 rounded text-sm font-bold ${
              autoTrade ? 'bg-green-600 text-white' : 'bg-slate-600 text-gray-300'
            }`}
          >
            {autoTrade ? 'ON' : 'OFF'}
          </button>
        </div>
        {extraInfo && (
          <div className="flex items-end">
            <div className="text-xs text-gray-500">{extraInfo}</div>
          </div>
        )}
      </div>
    </div>
  );
}
