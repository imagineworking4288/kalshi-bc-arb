import { useState } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { OpportunityList } from './components/opportunities/OpportunityList';
import { OpportunityDetail } from './components/opportunities/OpportunityDetail';
import { TradeModal } from './components/trading/TradeModal';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { AnalyticsDashboard } from './components/analytics/AnalyticsDashboard';
import { HistoryView } from './components/history/HistoryView';
import { useOpportunities } from './hooks/useOpportunities';
import { useWebSocket } from './hooks/useWebSocket';
import { useAlerts } from './hooks/useAlerts';

type Tab = 'opportunities' | 'analytics' | 'history';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('opportunities');
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Initialize data fetching and WebSocket
  useOpportunities();
  useWebSocket();
  useAlerts();

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col">
      {/* Header */}
      <Header onSettingsClick={() => setSettingsOpen(true)} />

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-6">
          {activeTab === 'opportunities' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <OpportunityList />
              <OpportunityDetail />
            </div>
          )}

          {activeTab === 'analytics' && <AnalyticsDashboard />}

          {activeTab === 'history' && <HistoryView />}
        </main>
      </div>

      {/* Modals */}
      <TradeModal />
      <SettingsPanel isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

export default App;
