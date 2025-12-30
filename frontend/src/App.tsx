import { useEffect, useState } from 'react';
import { Header } from './components/layout/Header';
import { TabNav } from './components/layout/TabNav';
import { OpportunitiesTab } from './components/opportunities/OpportunitiesTab';
import { TradingTab } from './components/trading/TradingTab';
import { AnalyticsTab } from './components/analytics/AnalyticsTab';
import { useTradingStore } from './stores/tradingStore';
import { api } from './services/api';

type Tab = 'opportunities' | 'trading' | 'analytics';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('opportunities');
  const setBalance = useTradingStore((s) => s.setBalance);
  const setMode = useTradingStore((s) => s.setMode);

  useEffect(() => {
    const init = async () => {
      try {
        const [config, balance] = await Promise.all([
          api.getConfig(),
          api.getBalance()
        ]);
        setMode(config.paper_mode ? 'paper' : 'live');
        setBalance(balance);
      } catch (err) {
        console.error('Init error:', err);
      }
    };
    init();
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <Header />
      <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="container mx-auto px-4 py-6">
        {activeTab === 'opportunities' && <OpportunitiesTab />}
        {activeTab === 'trading' && <TradingTab />}
        {activeTab === 'analytics' && <AnalyticsTab />}
      </main>
    </div>
  );
}

export default App;
