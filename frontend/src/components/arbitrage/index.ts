/**
 * Arbitrage components index file.
 * Exports all components for the arbitrage prediction trading system.
 */

export { PredictionTab } from './PredictionTab';
export { RiskDashboard } from './RiskDashboard';
export { ExecutionPanel } from './ExecutionPanel';
export { OrderBook } from './OrderBook';

// Re-export hooks
export {
  useOpportunities,
  useWebSocket,
  useRiskDashboard,
  useExecution,
  useTradingMode,
  useSystemStatus,
  usePositions,
} from './hooks/useArbitrage';

// Re-export types
export type {
  ArbitrageLeg,
  ArbitrageOpportunity,
  Orderbook,
  OrderbookLevel,
  CircuitBreakerStatus,
  RiskDashboard as RiskDashboardData,
  ExecutionResult,
} from './hooks/useArbitrage';
