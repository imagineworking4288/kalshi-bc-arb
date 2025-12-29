import { BarChart3, Clock, TrendingUp, History } from 'lucide-react';
import { clsx } from 'clsx';
import { useOpportunityStore } from '../../stores/opportunityStore';

type Tab = 'opportunities' | 'analytics' | 'history';

interface SidebarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const { spotPrices, lastUpdated } = useOpportunityStore();

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const tabs = [
    { id: 'opportunities' as Tab, icon: TrendingUp, label: 'Opportunities' },
    { id: 'analytics' as Tab, icon: BarChart3, label: 'Analytics' },
    { id: 'history' as Tab, icon: History, label: 'History' },
  ];

  return (
    <aside className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
      {/* Navigation */}
      <nav className="p-4 space-y-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={clsx(
              'w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors',
              activeTab === tab.id
                ? 'bg-emerald-600 text-white'
                : 'text-gray-400 hover:bg-gray-700 hover:text-white'
            )}
          >
            <tab.icon className="w-5 h-5" />
            <span className="font-medium">{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* Divider */}
      <div className="border-t border-gray-700 mx-4" />

      {/* Spot prices */}
      <div className="p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">
          Spot Prices
        </h3>
        <div className="space-y-2">
          {Object.entries(spotPrices).map(([asset, data]) => (
            <div
              key={asset}
              className="flex items-center justify-between p-2 bg-gray-700/50 rounded-lg"
            >
              <span className="text-sm font-medium text-gray-300">{asset}</span>
              <span className="text-sm font-mono text-white">
                {formatPrice(data.price)}
              </span>
            </div>
          ))}
          {Object.keys(spotPrices).length === 0 && (
            <p className="text-sm text-gray-500">No price data</p>
          )}
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <Clock className="w-3 h-3" />
          <span>
            {lastUpdated ? `Updated ${formatTime(lastUpdated)}` : 'No updates'}
          </span>
        </div>
      </div>
    </aside>
  );
}
