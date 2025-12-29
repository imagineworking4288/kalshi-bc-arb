// Configuration
export interface Config {
  environment: 'demo' | 'production';
  kalshiConnected: boolean;
  spotPricesEnabled: boolean;
}

// Spot prices
export interface SpotPrice {
  price: number;
  timestamp: string;
  cached: boolean;
}

export type SpotPrices = Record<string, SpotPrice>;

// Markets
export interface ThresholdMarket {
  ticker: string;
  title: string;
  strike: number;
  direction: 'above' | 'below';
  yesPrice: number;
  yesAsk: number;
  yesBid: number;
  volume: number;
}

export interface BracketMarket {
  ticker: string;
  title: string;
  lowBound: number;
  highBound: number;
  yesPrice: number;
  yesAsk: number;
  yesBid: number;
  volume: number;
}

export interface MarketGroup {
  asset: string;
  settlementTime: string;
  spotPrice: number | null;
  isComplete: boolean;
  thresholds: ThresholdMarket[];
  brackets: BracketMarket[];
}

// Opportunities
export interface RequiredBracket {
  ticker: string;
  title: string;
  lowBound: number;
  highBound: number;
  yesPrice: number;
  yesAsk: number;
}

export interface Opportunity {
  id: string;
  asset: string;
  settlementTime: string;
  detectedAt: string;
  thresholdTicker: string;
  thresholdTitle: string;
  thresholdStrike: number;
  thresholdDirection: string;
  thresholdYesPrice: number;
  impliedPrice: number;
  divergence: number;
  grossProfitPct: number;
  estimatedFees: number;
  netProfitPct: number;
  spotPrice: number | null;
  spotRelation: 'above' | 'below' | 'unknown';
  distanceFromThreshold: number | null;
  maxLiquidityUsd: number;
  maxLiquidityContracts: number;
  limitingLeg: string;
  tradeDirection: string;
  score: number;
  requiredBrackets: RequiredBracket[];
}

// Trading
export interface SizingSuggestions {
  conservative: number;
  moderate: number;
  aggressive: number;
  kelly: number;
  maxLiquidity: number;
}

export interface OrderResult {
  ticker: string;
  orderId: string;
  status: 'filled' | 'partial' | 'rejected';
  filled: number;
  requested: number;
}

export interface TradeResult {
  tradeId: string;
  status: 'success' | 'partial' | 'failed';
  totalCost: number;
  totalFees: number;
  expectedPayout: number;
  expectedProfit: number;
  message: string;
  orders: OrderResult[];
}

export interface TradeDetails {
  contracts: number;
  costPerSet: number;
  totalCost: number;
  totalFees: number;
  totalInvestment: number;
  guaranteedPayout: number;
  netProfit: number;
  netProfitPct: number;
  tradeDirection: string;
}

// Analytics
export interface AnalyticsSummary {
  totalOpportunities: number;
  avgProfitPct: number;
  maxProfitPct: number;
  minProfitPct: number;
  avgDurationSeconds: number;
  tradedCount: number;
  avgLiquidityUsd: number;
}

export interface AssetBreakdown {
  asset: string;
  count: number;
  avgProfitPct: number;
  avgDurationSeconds: number;
  tradedCount: number;
}

export interface DateBreakdown {
  date: string;
  count: number;
  avgProfitPct: number;
  tradedCount: number;
}

export interface HourBreakdown {
  hour: number;
  count: number;
  avgProfitPct: number;
}

export interface ProfitDistribution {
  binStart: number;
  binEnd: number;
  count: number;
}

export interface TradePerformance {
  totalTrades: number;
  successfulTrades: number;
  failedTrades: number;
  successRate: number;
  totalInvested: number;
  totalProfit: number;
  avgProfitPerTrade: number;
}

export interface PnLSummary {
  totalTrades: number;
  settledTrades: number;
  totalInvested: number;
  totalExpectedProfit: number;
  realizedProfit: number;
  unrealizedProfit: number;
}

// Settings
export interface AlertSettings {
  minProfitPct: number;
  minLiquidityUsd: number;
  visualHighlight: boolean;
  audioEnabled: boolean;
  audioSound: 'alert' | 'chime' | 'ding';
  audioVolume: number;
  browserNotifications: boolean;
}

export interface RiskSettings {
  maxPositionPerMarket: number;
  maxTotalExposure: number;
  maxDailyLoss: number;
  maxSingleTrade: number;
}

// Balance
export interface Balance {
  availableBalance: number;
  totalBalance: number;
}

// History
export interface HistoricalOpportunity {
  id: string;
  detectedAt: string;
  closedAt: string | null;
  asset: string;
  settlementTime: string;
  thresholdTicker: string;
  thresholdStrike: number;
  thresholdDirection: string;
  thresholdYesPrice: number;
  impliedPrice: number;
  divergence: number;
  spotPrice: number | null;
  grossProfitPct: number;
  estimatedFees: number;
  netProfitPct: number;
  maxLiquidityUsd: number;
  tradeDirection: string;
  wasTraded: boolean;
  tradeId: string | null;
  durationSeconds: number | null;
}

export interface HistoricalTrade {
  id: string;
  opportunityId: string;
  executedAt: string;
  asset: string;
  totalCost: number;
  totalFees: number;
  expectedPayout: number;
  expectedProfit: number;
  status: string;
  actualCost: number | null;
  actualFees: number | null;
  settledAt: string | null;
  actualPayout: number | null;
  actualProfit: number | null;
}
