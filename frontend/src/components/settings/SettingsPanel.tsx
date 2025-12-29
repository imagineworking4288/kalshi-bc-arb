import { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useSettingsStore } from '../../stores/settingsStore';

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const {
    environment,
    alertSettings,
    riskSettings,
    setEnvironment,
    setAlertSettings,
    setRiskSettings,
    resetToDefaults,
  } = useSettingsStore();

  const [showEnvConfirm, setShowEnvConfirm] = useState(false);
  const [pendingEnv, setPendingEnv] = useState<'demo' | 'production' | null>(null);

  const handleEnvChange = (newEnv: 'demo' | 'production') => {
    if (newEnv === 'production') {
      setPendingEnv(newEnv);
      setShowEnvConfirm(true);
    } else {
      setEnvironment(newEnv);
    }
  };

  const confirmEnvChange = () => {
    if (pendingEnv) {
      setEnvironment(pendingEnv);
    }
    setShowEnvConfirm(false);
    setPendingEnv(null);
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title="Settings" size="lg">
        <div className="space-y-8">
          {/* Environment */}
          <section>
            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-4">
              Environment
            </h3>
            <div className="flex gap-3">
              <button
                onClick={() => handleEnvChange('demo')}
                className={`flex-1 p-4 rounded-lg border-2 transition-colors ${
                  environment === 'demo'
                    ? 'border-blue-500 bg-blue-900/20'
                    : 'border-gray-600 hover:border-gray-500'
                }`}
              >
                <p className="font-medium text-white">Demo</p>
                <p className="text-xs text-gray-400 mt-1">
                  Practice with simulated money
                </p>
              </button>
              <button
                onClick={() => handleEnvChange('production')}
                className={`flex-1 p-4 rounded-lg border-2 transition-colors ${
                  environment === 'production'
                    ? 'border-red-500 bg-red-900/20'
                    : 'border-gray-600 hover:border-gray-500'
                }`}
              >
                <p className="font-medium text-white">Production</p>
                <p className="text-xs text-gray-400 mt-1">Trade with real money</p>
              </button>
            </div>
          </section>

          {/* Alert Settings */}
          <section>
            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-4">
              Alert Settings
            </h3>
            <div className="space-y-4">
              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">
                    Minimum Profit % for Alert
                  </span>
                  <input
                    type="number"
                    value={alertSettings.minProfitPct}
                    onChange={(e) =>
                      setAlertSettings({ minProfitPct: parseFloat(e.target.value) })
                    }
                    className="w-20 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-right"
                    step="0.5"
                    min="0"
                  />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">
                    Minimum Liquidity (USD)
                  </span>
                  <input
                    type="number"
                    value={alertSettings.minLiquidityUsd}
                    onChange={(e) =>
                      setAlertSettings({
                        minLiquidityUsd: parseFloat(e.target.value),
                      })
                    }
                    className="w-24 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-right"
                    step="10"
                    min="0"
                  />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">Visual Highlight</span>
                  <input
                    type="checkbox"
                    checked={alertSettings.visualHighlight}
                    onChange={(e) =>
                      setAlertSettings({ visualHighlight: e.target.checked })
                    }
                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-emerald-500 focus:ring-emerald-500"
                  />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">Audio Alerts</span>
                  <input
                    type="checkbox"
                    checked={alertSettings.audioEnabled}
                    onChange={(e) =>
                      setAlertSettings({ audioEnabled: e.target.checked })
                    }
                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-emerald-500 focus:ring-emerald-500"
                  />
                </label>
              </div>

              {alertSettings.audioEnabled && (
                <div className="ml-4 space-y-3">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">
                      Sound
                    </label>
                    <select
                      value={alertSettings.audioSound}
                      onChange={(e) =>
                        setAlertSettings({
                          audioSound: e.target.value as 'alert' | 'chime' | 'ding',
                        })
                      }
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
                    >
                      <option value="chime">Chime</option>
                      <option value="alert">Alert</option>
                      <option value="ding">Ding</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-2">
                      Volume: {alertSettings.audioVolume}%
                    </label>
                    <input
                      type="range"
                      value={alertSettings.audioVolume}
                      onChange={(e) =>
                        setAlertSettings({
                          audioVolume: parseInt(e.target.value),
                        })
                      }
                      min="0"
                      max="100"
                      className="w-full"
                    />
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Risk Settings */}
          <section>
            <h3 className="text-sm font-semibold text-gray-400 uppercase mb-4">
              Risk Limits
            </h3>
            <div className="space-y-4">
              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">
                    Max Position per Market ($)
                  </span>
                  <input
                    type="number"
                    value={riskSettings.maxPositionPerMarket}
                    onChange={(e) =>
                      setRiskSettings({
                        maxPositionPerMarket: parseFloat(e.target.value),
                      })
                    }
                    className="w-24 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-right"
                    step="50"
                    min="0"
                  />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">
                    Max Total Exposure ($)
                  </span>
                  <input
                    type="number"
                    value={riskSettings.maxTotalExposure}
                    onChange={(e) =>
                      setRiskSettings({
                        maxTotalExposure: parseFloat(e.target.value),
                      })
                    }
                    className="w-24 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-right"
                    step="100"
                    min="0"
                  />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">Max Single Trade ($)</span>
                  <input
                    type="number"
                    value={riskSettings.maxSingleTrade}
                    onChange={(e) =>
                      setRiskSettings({
                        maxSingleTrade: parseFloat(e.target.value),
                      })
                    }
                    className="w-24 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-right"
                    step="25"
                    min="0"
                  />
                </label>
              </div>

              <div>
                <label className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">Max Daily Loss ($)</span>
                  <input
                    type="number"
                    value={riskSettings.maxDailyLoss}
                    onChange={(e) =>
                      setRiskSettings({
                        maxDailyLoss: parseFloat(e.target.value),
                      })
                    }
                    className="w-24 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-right"
                    step="25"
                    min="0"
                  />
                </label>
              </div>
            </div>
          </section>

          {/* Actions */}
          <div className="flex justify-between pt-4 border-t border-gray-700">
            <Button variant="ghost" onClick={resetToDefaults}>
              Reset to Defaults
            </Button>
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        isOpen={showEnvConfirm}
        onClose={() => setShowEnvConfirm(false)}
        onConfirm={confirmEnvChange}
        title="Switch to Production?"
        message="You're about to switch to production mode. This will use real money for trading. Make sure you understand the risks."
        confirmText="Switch to Production"
        variant="danger"
      />
    </>
  );
}
