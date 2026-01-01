import clsx from 'clsx';

type Tab = 'trade' | 'portfolio' | 'watchlist' | 'opportunities' | 'trading' | 'analytics' | 'autotrader';

interface Props {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export function TabNav({ activeTab, onTabChange }: Props) {
  const tabs: { id: Tab; label: string }[] = [
    { id: 'trade', label: 'Trade' },
    { id: 'portfolio', label: 'Portfolio' },
    { id: 'watchlist', label: 'Watchlist' },
    { id: 'opportunities', label: 'Arbitrage' },
    { id: 'trading', label: 'Old Trading' },
    { id: 'analytics', label: 'Analytics' },
    { id: 'autotrader', label: 'Auto-Trader' },
  ];

  return (
    <nav className="bg-gray-800 border-b border-gray-700">
      <div className="container mx-auto px-4">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={clsx(
                'px-4 py-3 text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-white'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
