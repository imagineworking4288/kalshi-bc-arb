/**
 * Real-time orderbook display component.
 * Shows live bid/ask data for selected markets with WebSocket updates.
 */

import React, { useState, useMemo } from 'react';
import { useWebSocket, useOpportunities, Orderbook, OrderbookLevel } from './hooks/useArbitrage';

// ============ Sub-components ============

interface OrderbookLevelRowProps {
  level: OrderbookLevel;
  side: 'bid' | 'ask';
  maxQuantity: number;
}

const OrderbookLevelRow: React.FC<OrderbookLevelRowProps> = ({
  level,
  side,
  maxQuantity,
}) => {
  const barWidth = maxQuantity > 0 ? (level.quantity / maxQuantity) * 100 : 0;

  return (
    <div className="relative flex items-center py-1 px-2">
      {/* Background bar */}
      <div
        className={`absolute inset-y-0 ${
          side === 'bid' ? 'left-0 bg-green-900/30' : 'right-0 bg-red-900/30'
        }`}
        style={{ width: `${barWidth}%` }}
      />

      {/* Content */}
      <div className="relative flex w-full items-center justify-between text-sm">
        {side === 'bid' ? (
          <>
            <span className="text-gray-400 w-16">{level.quantity}</span>
            <span className="text-green-400 font-mono">{level.price_cents}¢</span>
          </>
        ) : (
          <>
            <span className="text-red-400 font-mono">{level.price_cents}¢</span>
            <span className="text-gray-400 w-16 text-right">{level.quantity}</span>
          </>
        )}
      </div>
    </div>
  );
};

interface SingleOrderbookProps {
  ticker: string;
  orderbook: Orderbook | null;
  loading: boolean;
}

const SingleOrderbook: React.FC<SingleOrderbookProps> = ({
  ticker,
  orderbook,
  loading,
}) => {
  const maxBidQty = useMemo(() => {
    if (!orderbook?.yes_bids) return 0;
    return Math.max(...orderbook.yes_bids.map((l) => l.quantity), 1);
  }, [orderbook?.yes_bids]);

  const maxAskQty = useMemo(() => {
    if (!orderbook?.no_bids) return 0;
    return Math.max(...orderbook.no_bids.map((l) => l.quantity), 1);
  }, [orderbook?.no_bids]);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-700 rounded w-1/3 mb-4"></div>
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-6 bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 bg-gray-700 flex justify-between items-center">
        <span className="font-semibold text-white truncate">{ticker}</span>
        {orderbook?.is_stale && (
          <span className="text-xs text-yellow-400 px-2 py-0.5 bg-yellow-900/30 rounded">
            STALE
          </span>
        )}
      </div>

      {/* Orderbook Content */}
      <div className="grid grid-cols-2 divide-x divide-gray-700">
        {/* YES Bids */}
        <div className="p-2">
          <div className="text-xs text-gray-400 uppercase mb-2 px-2 flex justify-between">
            <span>Qty</span>
            <span>YES Bid</span>
          </div>
          <div className="space-y-0.5">
            {orderbook?.yes_bids?.length ? (
              orderbook.yes_bids.slice(0, 5).map((level, i) => (
                <OrderbookLevelRow
                  key={i}
                  level={level}
                  side="bid"
                  maxQuantity={maxBidQty}
                />
              ))
            ) : (
              <div className="text-center text-gray-500 text-sm py-4">No bids</div>
            )}
          </div>
        </div>

        {/* NO Bids (shown as asks) */}
        <div className="p-2">
          <div className="text-xs text-gray-400 uppercase mb-2 px-2 flex justify-between">
            <span>NO Bid</span>
            <span>Qty</span>
          </div>
          <div className="space-y-0.5">
            {orderbook?.no_bids?.length ? (
              orderbook.no_bids.slice(0, 5).map((level, i) => (
                <OrderbookLevelRow
                  key={i}
                  level={level}
                  side="ask"
                  maxQuantity={maxAskQty}
                />
              ))
            ) : (
              <div className="text-center text-gray-500 text-sm py-4">No asks</div>
            )}
          </div>
        </div>
      </div>

      {/* Spread */}
      <div className="px-4 py-2 bg-gray-750 border-t border-gray-700 flex justify-between text-sm">
        <span className="text-gray-400">Best YES:</span>
        <span className="text-green-400">
          {orderbook?.yes_ask ? `${orderbook.yes_ask}¢` : '--'}
        </span>
        <span className="text-gray-400">Best NO:</span>
        <span className="text-red-400">
          {orderbook?.no_ask ? `${orderbook.no_ask}¢` : '--'}
        </span>
      </div>

      {/* Timestamp */}
      {orderbook?.timestamp && (
        <div className="px-4 py-1 text-xs text-gray-500 text-center border-t border-gray-700">
          Updated: {new Date(orderbook.timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
};

interface OrderbookSummaryProps {
  brackets: Array<{
    ticker: string;
    low: number;
    high: number;
    yes_price: number;
  }>;
  orderbooks: Record<string, Orderbook>;
}

const OrderbookSummary: React.FC<OrderbookSummaryProps> = ({
  brackets,
  orderbooks,
}) => {
  const totalYesAsk = brackets.reduce((sum, b) => {
    const ob = orderbooks[b.ticker];
    return sum + (ob?.yes_ask || Math.round(b.yes_price * 100));
  }, 0);

  // Note: totalNoBid available if needed for future NO-side display
  // const totalNoBid = brackets.reduce((sum, b) => {
  //   const ob = orderbooks[b.ticker];
  //   return sum + (100 - (ob?.yes_ask || Math.round(b.yes_price * 100)));
  // }, 0);

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h4 className="font-semibold text-white mb-3">Summary</h4>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-gray-400">Total YES Cost</div>
          <div className="text-green-400 font-semibold">
            ${(totalYesAsk / 100).toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-gray-400">Guaranteed Payout</div>
          <div className="text-white font-semibold">$1.00</div>
        </div>
        <div>
          <div className="text-gray-400">Gross Profit</div>
          <div
            className={`font-semibold ${
              100 - totalYesAsk > 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            ${((100 - totalYesAsk) / 100).toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-gray-400">ROI</div>
          <div
            className={`font-semibold ${
              100 - totalYesAsk > 0 ? 'text-green-400' : 'text-red-400'
            }`}
          >
            {totalYesAsk > 0
              ? (((100 - totalYesAsk) / totalYesAsk) * 100).toFixed(1)
              : 0}
            %
          </div>
        </div>
      </div>
    </div>
  );
};

// ============ Main Component ============

export const OrderBook: React.FC = () => {
  const { opportunities } = useOpportunities(0);
  const [selectedEventTicker, setSelectedEventTicker] = useState<string>('');

  // Get unique event tickers
  const eventTickers = useMemo(() => {
    const tickers = new Set<string>();
    opportunities.forEach((opp) => {
      const ticker = opp.event_ticker || opp.id;
      if (ticker) tickers.add(ticker);
    });
    return Array.from(tickers);
  }, [opportunities]);

  // Subscribe to selected event
  const { connected, orderbooks } = useWebSocket(
    selectedEventTicker ? [selectedEventTicker] : []
  );

  // Get selected opportunity
  const selectedOpp = useMemo(() => {
    return opportunities.find(
      (opp) => (opp.event_ticker || opp.id) === selectedEventTicker
    );
  }, [opportunities, selectedEventTicker]);

  // Get market tickers for the selected opportunity
  const marketTickers = useMemo(() => {
    if (!selectedOpp) return [];
    return (
      selectedOpp.brackets?.map((b) => b.ticker) ||
      selectedOpp.legs?.map((l) => l.ticker) ||
      []
    );
  }, [selectedOpp]);

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white">Order Book</h2>
          <p className="text-sm text-gray-400">
            Real-time market depth for selected opportunities
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-sm text-gray-400">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Event Selector */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <label className="block text-sm text-gray-400 mb-2">Select Event</label>
        <select
          value={selectedEventTicker}
          onChange={(e) => setSelectedEventTicker(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white"
        >
          <option value="">-- Select an event --</option>
          {eventTickers.map((ticker) => {
            const opp = opportunities.find(
              (o) => (o.event_ticker || o.id) === ticker
            );
            return (
              <option key={ticker} value={ticker}>
                {opp?.event_title || opp?.threshold_title || ticker}
              </option>
            );
          })}
        </select>
      </div>

      {/* No Selection State */}
      {!selectedEventTicker && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-lg mb-2">Select an event to view orderbooks</div>
          <div className="text-sm">
            Orderbooks show real-time bid/ask data for each market
          </div>
        </div>
      )}

      {/* Summary Card */}
      {selectedOpp && selectedOpp.brackets && (
        <OrderbookSummary
          brackets={selectedOpp.brackets}
          orderbooks={orderbooks}
        />
      )}

      {/* Orderbook Grid */}
      {selectedEventTicker && marketTickers.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {marketTickers.map((ticker) => (
            <SingleOrderbook
              key={ticker}
              ticker={ticker}
              orderbook={orderbooks[ticker] || null}
              loading={false}
            />
          ))}
        </div>
      )}

      {/* No Markets State */}
      {selectedEventTicker && marketTickers.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-lg">No markets found for this event</div>
        </div>
      )}

      {/* WebSocket Status */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h4 className="font-semibold text-white mb-3">WebSocket Status</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-400">Connection</div>
            <div
              className={`font-semibold ${
                connected ? 'text-green-400' : 'text-red-400'
              }`}
            >
              {connected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
          <div>
            <div className="text-gray-400">Subscribed Events</div>
            <div className="text-white">{selectedEventTicker ? 1 : 0}</div>
          </div>
          <div>
            <div className="text-gray-400">Active Orderbooks</div>
            <div className="text-white">{Object.keys(orderbooks).length}</div>
          </div>
          <div>
            <div className="text-gray-400">Markets Tracked</div>
            <div className="text-white">{marketTickers.length}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OrderBook;
