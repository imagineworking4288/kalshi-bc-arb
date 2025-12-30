import { useEffect } from 'react';
import { useOpportunityStore } from '../../stores/opportunityStore';
import { useTradingStore } from '../../stores/tradingStore';
import { api } from '../../services/api';
import { OpportunityCard } from './OpportunityCard';
import { ExecuteModal } from './ExecuteModal';

export function OpportunitiesTab() {
  const { opportunities, loading, error, setOpportunities, setSpotPrice, setLoading, setError } = useOpportunityStore();
  const executeModalOpen = useTradingStore((s) => s.executeModalOpen);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [oppsRes, spotRes] = await Promise.all([
        api.getOpportunities(),
        api.getSpotPrice().catch(() => null)
      ]);
      setOpportunities(oppsRes.opportunities);
      if (spotRes) setSpotPrice(spotRes.price);
    } catch (err: any) {
      setError(err.message);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Arbitrage Opportunities</h2>
        <button
          onClick={fetchData}
          disabled={loading}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-900/50 border border-red-600 rounded-lg text-red-200">
          {error}
        </div>
      )}

      {!loading && opportunities.length === 0 && !error && (
        <div className="text-center py-12 text-gray-400">
          No arbitrage opportunities detected. Markets are efficiently priced.
        </div>
      )}

      <div className="space-y-4">
        {opportunities.map((opp) => (
          <OpportunityCard key={opp.id} opportunity={opp} />
        ))}
      </div>

      {executeModalOpen && <ExecuteModal />}
    </div>
  );
}
