/**
 * Risk monitoring dashboard component.
 * Shows P&L, positions, circuit breaker status, and risk metrics.
 */

import React, { useState } from 'react';
import { useRiskDashboard, usePositions } from './hooks/useArbitrage';

// ============ Utility Functions ============

function formatCurrency(cents: number): string {
  const dollars = cents / 100;
  return dollars >= 0 ? `$${dollars.toFixed(2)}` : `-$${Math.abs(dollars).toFixed(2)}`;
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

// ============ Sub-components ============

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  color?: 'green' | 'red' | 'yellow' | 'blue' | 'default';
  icon?: React.ReactNode;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subValue,
  color = 'default',
  icon,
}) => {
  const colorClasses = {
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    blue: 'text-blue-400',
    default: 'text-white',
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-1">
        {icon}
        {label}
      </div>
      <div className={`text-2xl font-bold ${colorClasses[color]}`}>
        {value}
      </div>
      {subValue && <div className="text-sm text-gray-500">{subValue}</div>}
    </div>
  );
};

interface CircuitBreakerCardProps {
  status: {
    can_trade: boolean;
    tripped: boolean;
    trip_reason: string | null;
    cooldown_until: string | null;
    daily_pnl_cents: number;
    total_position: number;
    consecutive_losses: number;
    win_rate: number;
    drawdown_percent: number;
    warnings: string[];
  };
  onReset: () => void;
  onTrip: () => void;
}

const CircuitBreakerCard: React.FC<CircuitBreakerCardProps> = ({
  status,
  onReset,
  onTrip,
}) => {
  const [resetting, setResetting] = useState(false);
  const [tripping, setTripping] = useState(false);

  const handleReset = async () => {
    setResetting(true);
    try {
      await onReset();
    } finally {
      setResetting(false);
    }
  };

  const handleTrip = async () => {
    setTripping(true);
    try {
      await onTrip();
    } finally {
      setTripping(false);
    }
  };

  return (
    <div
      className={`rounded-lg p-4 border-2 ${
        status.tripped
          ? 'border-red-500 bg-red-900/20'
          : status.warnings.length > 0
          ? 'border-yellow-500 bg-yellow-900/20'
          : 'border-green-500 bg-green-900/20'
      }`}
    >
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-semibold text-lg text-white">Circuit Breaker</h3>
        <span
          className={`px-3 py-1 rounded text-sm font-semibold ${
            status.can_trade
              ? 'bg-green-900/50 text-green-300'
              : 'bg-red-900/50 text-red-300'
          }`}
        >
          {status.can_trade ? 'ACTIVE' : 'TRIPPED'}
        </span>
      </div>

      {/* Status Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <div className="text-xs text-gray-400">Daily P&L</div>
          <div
            className={`font-semibold ${
              status.daily_pnl_cents >= 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {formatCurrency(status.daily_pnl_cents)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Win Rate</div>
          <div className="font-semibold text-white">
            {formatPercent(status.win_rate * 100)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Consecutive Losses</div>
          <div
            className={`font-semibold ${
              status.consecutive_losses > 2 ? 'text-red-400' : 'text-white'
            }`}
          >
            {status.consecutive_losses}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-400">Drawdown</div>
          <div
            className={`font-semibold ${
              status.drawdown_percent > 10 ? 'text-red-400' : 'text-white'
            }`}
          >
            {formatPercent(status.drawdown_percent)}
          </div>
        </div>
      </div>

      {/* Trip Reason */}
      {status.tripped && status.trip_reason && (
        <div className="mb-3 p-2 bg-red-900/30 rounded text-red-300 text-sm">
          <strong>Reason:</strong> {status.trip_reason}
        </div>
      )}

      {/* Cooldown */}
      {status.cooldown_until && (
        <div className="mb-3 text-sm text-gray-400">
          Cooldown until: {new Date(status.cooldown_until).toLocaleTimeString()}
        </div>
      )}

      {/* Warnings */}
      {status.warnings.length > 0 && (
        <div className="mb-3">
          {status.warnings.map((w, i) => (
            <div key={i} className="text-sm text-yellow-400">
              Warning: {w}
            </div>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2">
        {status.tripped ? (
          <button
            onClick={handleReset}
            disabled={resetting}
            className="flex-1 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-semibold disabled:opacity-50"
          >
            {resetting ? 'Resetting...' : 'Reset Circuit Breaker'}
          </button>
        ) : (
          <button
            onClick={handleTrip}
            disabled={tripping}
            className="flex-1 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-semibold disabled:opacity-50"
          >
            {tripping ? 'Tripping...' : 'Manual Trip'}
          </button>
        )}
      </div>
    </div>
  );
};

interface PositionRowProps {
  position: {
    ticker: string;
    side: string;
    contracts?: number;
    quantity?: number;
    avg_price?: number;
    avg_cost_cents?: number;
    total_cost?: number;
    unrealized_pnl_cents?: number;
    current_price?: number | null;
  };
}

const PositionRow: React.FC<PositionRowProps> = ({ position }) => {
  const quantity = position.contracts || position.quantity || 0;
  const avgPrice = position.avg_price || (position.avg_cost_cents || 0) / 100;
  const pnlCents = position.unrealized_pnl_cents || 0;

  return (
    <tr className="border-b border-gray-700">
      <td className="py-2 text-white">{position.ticker}</td>
      <td
        className={`py-2 ${
          position.side === 'yes' ? 'text-green-400' : 'text-red-400'
        }`}
      >
        {position.side.toUpperCase()}
      </td>
      <td className="py-2 text-right text-white">{quantity}</td>
      <td className="py-2 text-right text-gray-400">${avgPrice.toFixed(2)}</td>
      <td
        className={`py-2 text-right ${
          pnlCents >= 0 ? 'text-green-400' : 'text-red-400'
        }`}
      >
        {formatCurrency(pnlCents)}
      </td>
    </tr>
  );
};

// ============ Main Component ============

export const RiskDashboard: React.FC = () => {
  const {
    risk,
    loading: riskLoading,
    error: riskError,
    refresh: refreshRisk,
    resetCircuitBreaker,
    tripCircuitBreaker,
  } = useRiskDashboard();

  const {
    positions,
    loading: positionsLoading,
    error: positionsError,
    refresh: refreshPositions,
  } = usePositions();

  const handleRefresh = () => {
    refreshRisk();
    refreshPositions();
  };

  if (riskLoading && !risk) {
    return (
      <div className="p-4">
        <div className="text-center py-12 text-gray-400">
          <div className="animate-pulse">Loading risk data...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white">Risk Dashboard</h2>
          <p className="text-sm text-gray-400">
            Last updated:{' '}
            {risk?.timestamp
              ? new Date(risk.timestamp).toLocaleTimeString()
              : 'Never'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span
            className={`px-3 py-1 rounded text-sm font-semibold ${
              risk?.trading_mode === 'paper'
                ? 'bg-yellow-900/50 text-yellow-300'
                : 'bg-red-900/50 text-red-300'
            }`}
          >
            {(risk?.trading_mode || 'PAPER').toUpperCase()} MODE
          </span>
          <button
            onClick={handleRefresh}
            disabled={riskLoading}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Error Display */}
      {(riskError || positionsError) && (
        <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">
          {riskError || positionsError}
        </div>
      )}

      {/* Main Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Balance"
          value={formatCurrency(risk?.balance_cents || 0)}
          color="default"
        />
        <MetricCard
          label="Daily P&L"
          value={formatCurrency(risk?.daily_pnl_cents || 0)}
          color={
            (risk?.daily_pnl_cents || 0) >= 0
              ? 'green'
              : 'red'
          }
        />
        <MetricCard
          label="Total P&L"
          value={formatCurrency(risk?.total_pnl_cents || 0)}
          color={
            (risk?.total_pnl_cents || 0) >= 0
              ? 'green'
              : 'red'
          }
        />
        <MetricCard
          label="Unrealized"
          value={formatCurrency(risk?.unrealized_pnl_cents || 0)}
          color={
            (risk?.unrealized_pnl_cents || 0) >= 0
              ? 'green'
              : 'red'
          }
        />
      </div>

      {/* Performance Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Trades Today"
          value={risk?.trades_today || 0}
          color="blue"
        />
        <MetricCard
          label="Wins"
          value={risk?.wins_today || 0}
          color="green"
        />
        <MetricCard
          label="Losses"
          value={risk?.losses_today || 0}
          color="red"
        />
        <MetricCard
          label="Win Rate"
          value={formatPercent((risk?.win_rate || 0.5) * 100)}
          color={
            (risk?.win_rate || 0.5) >= 0.5
              ? 'green'
              : 'red'
          }
        />
      </div>

      {/* Circuit Breaker */}
      {risk?.circuit_breaker && (
        <CircuitBreakerCard
          status={risk.circuit_breaker}
          onReset={resetCircuitBreaker}
          onTrip={() => tripCircuitBreaker('Manual trip from dashboard')}
        />
      )}

      {/* Positions Table */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-lg text-white">Open Positions</h3>
          <span className="text-sm text-gray-400">
            {positions.length} position{positions.length !== 1 ? 's' : ''}
          </span>
        </div>

        {positionsLoading && positions.length === 0 ? (
          <div className="text-center py-4 text-gray-400">Loading positions...</div>
        ) : positions.length === 0 ? (
          <div className="text-center py-4 text-gray-400">No open positions</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400">
                  <th className="text-left py-2">Ticker</th>
                  <th className="text-left py-2">Side</th>
                  <th className="text-right py-2">Quantity</th>
                  <th className="text-right py-2">Avg Price</th>
                  <th className="text-right py-2">Unrealized P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, i) => (
                  <PositionRow key={pos.id || pos.ticker || i} position={pos} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Risk Thresholds Info */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h3 className="font-semibold text-lg text-white mb-3">Risk Thresholds</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-400">Max Daily Loss</div>
            <div className="text-white font-semibold">$50.00</div>
          </div>
          <div>
            <div className="text-gray-400">Max Position Size</div>
            <div className="text-white font-semibold">100 contracts</div>
          </div>
          <div>
            <div className="text-gray-400">Max Consecutive Losses</div>
            <div className="text-white font-semibold">5</div>
          </div>
          <div>
            <div className="text-gray-400">Max Drawdown</div>
            <div className="text-white font-semibold">20%</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RiskDashboard;
