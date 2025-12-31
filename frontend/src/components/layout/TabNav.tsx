import clsx from 'clsx';

type Tab = 'opportunities' | 'trading' | 'analytics' | 'trade';

interface Props {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export function TabNav({ activeTab, onTabChange }: Props) {
  const tabs: { id: Tab; label: string }[] = [
    { id: 'opportunities', label: 'Opportunities' },
    { id: 'trade', label: 'Trade (MVP)' },
    { id: 'trading', label: 'Trading' },
    { id: 'analytics', label: 'Analytics' },
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
