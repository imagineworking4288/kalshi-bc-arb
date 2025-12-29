import { useOpportunityStore } from '../../stores/opportunityStore';
import { OpportunityCard } from './OpportunityCard';
import { LoadingSpinner } from '../common/LoadingSpinner';

export function OpportunityList() {
  const { opportunities, isLoading, error, selectedOpportunityId, selectOpportunity } =
    useOpportunityStore();

  if (isLoading && opportunities.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 text-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  if (opportunities.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-8 text-center">
        <p className="text-gray-400">No arbitrage opportunities detected</p>
        <p className="text-sm text-gray-500 mt-2">
          Opportunities appear when threshold and bracket prices diverge
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">
          Opportunities ({opportunities.length})
        </h2>
      </div>

      <div className="space-y-2">
        {opportunities.map((opp) => (
          <OpportunityCard
            key={opp.id}
            opportunity={opp}
            isSelected={opp.id === selectedOpportunityId}
            onClick={() =>
              selectOpportunity(opp.id === selectedOpportunityId ? null : opp.id)
            }
          />
        ))}
      </div>
    </div>
  );
}
