import { Settings, Wallet, Wifi, WifiOff } from 'lucide-react';
import { Badge } from '../common/Badge';
import { useOpportunityStore } from '../../stores/opportunityStore';
import { useSettingsStore } from '../../stores/settingsStore';

interface HeaderProps {
  onSettingsClick: () => void;
}

export function Header({ onSettingsClick }: HeaderProps) {
  const { balance, connectionStatus } = useOpportunityStore();
  const { environment } = useSettingsStore();

  const formatBalance = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  return (
    <header className="bg-gray-800 border-b border-gray-700 px-4 py-3">
      <div className="flex items-center justify-between">
        {/* Logo and title */}
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-white">Kalshi Arb Scanner</h1>
          <Badge variant={environment === 'demo' ? 'info' : 'danger'} size="sm">
            {environment.toUpperCase()}
          </Badge>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-4">
          {/* Connection status */}
          <div className="flex items-center gap-2 text-sm">
            {connectionStatus === 'connected' ? (
              <>
                <Wifi className="w-4 h-4 text-emerald-500" />
                <span className="text-emerald-500">Live</span>
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-gray-500" />
                <span className="text-gray-500">Offline</span>
              </>
            )}
          </div>

          {/* Balance */}
          {balance && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 rounded-lg">
              <Wallet className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-white">
                {formatBalance(balance.availableBalance)}
              </span>
            </div>
          )}

          {/* Settings button */}
          <button
            onClick={onSettingsClick}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
