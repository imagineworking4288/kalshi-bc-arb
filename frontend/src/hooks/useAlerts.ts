import { useEffect, useRef } from 'react';
import { useOpportunityStore } from '../stores/opportunityStore';
import { useSettingsStore } from '../stores/settingsStore';
import type { Opportunity } from '../types';

export function useAlerts() {
  const { opportunities } = useOpportunityStore();
  const { alertSettings } = useSettingsStore();
  const previousOppsRef = useRef<string[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Request notification permission on mount
  useEffect(() => {
    if (alertSettings.browserNotifications && 'Notification' in window) {
      Notification.requestPermission();
    }
  }, [alertSettings.browserNotifications]);

  // Check for new opportunities
  useEffect(() => {
    const currentIds = opportunities.map((o) => o.id);
    const previousIds = previousOppsRef.current;

    // Find new opportunities that meet alert criteria
    const newOpps = opportunities.filter(
      (o) =>
        !previousIds.includes(o.id) &&
        o.netProfitPct >= alertSettings.minProfitPct &&
        o.maxLiquidityUsd >= alertSettings.minLiquidityUsd
    );

    if (newOpps.length > 0) {
      // Play audio alert
      if (alertSettings.audioEnabled) {
        playAlert();
      }

      // Show browser notification
      if (alertSettings.browserNotifications && Notification.permission === 'granted') {
        newOpps.forEach((opp) => {
          showNotification(opp);
        });
      }
    }

    previousOppsRef.current = currentIds;
  }, [opportunities, alertSettings]);

  const playAlert = () => {
    if (!audioRef.current) {
      audioRef.current = new Audio(`/sounds/${alertSettings.audioSound}.mp3`);
    } else {
      audioRef.current.src = `/sounds/${alertSettings.audioSound}.mp3`;
    }

    audioRef.current.volume = alertSettings.audioVolume / 100;
    audioRef.current.play().catch((err) => {
      console.warn('Failed to play alert sound:', err);
    });
  };

  const showNotification = (opportunity: Opportunity) => {
    new Notification('New Arbitrage Opportunity', {
      body: `${opportunity.asset} - ${opportunity.netProfitPct.toFixed(2)}% profit potential`,
      icon: '/icon.png',
      tag: opportunity.id,
    });
  };

  return {
    playAlert,
    showNotification,
  };
}
