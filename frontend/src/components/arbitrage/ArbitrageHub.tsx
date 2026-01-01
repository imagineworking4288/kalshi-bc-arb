import { useState } from 'react';
import { CryptoArbitrageSection } from './CryptoArbitrageSection';
import { WeatherArbitrageSection } from './WeatherArbitrageSection';

type SectionType = 'crypto' | 'weather' | 'economic';

export function ArbitrageHub() {
  const [activeSection, setActiveSection] = useState<SectionType>('crypto');

  return (
    <div className="p-4 space-y-4">
      {/* Main Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-white">Arbitrage Scanner</h2>
          <p className="text-sm text-gray-400">
            Multi-market arbitrage detection and execution
          </p>
        </div>
      </div>

      {/* Sub-Navigation */}
      <div className="flex border-b border-slate-700 gap-1">
        {[
          { key: 'crypto', label: 'Crypto', enabled: true },
          { key: 'weather', label: 'Weather', enabled: true },
          { key: 'economic', label: 'Economic', enabled: false }
        ].map(section => (
          <button
            key={section.key}
            onClick={() => section.enabled && setActiveSection(section.key as SectionType)}
            disabled={!section.enabled}
            className={`px-4 py-2 text-sm font-medium transition-colors relative ${
              activeSection === section.key
                ? 'text-blue-400'
                : section.enabled
                ? 'text-gray-400 hover:text-gray-300'
                : 'text-gray-600 cursor-not-allowed'
            }`}
          >
            {section.label}
            {!section.enabled && (
              <span className="ml-1 text-xs text-gray-600">(Soon)</span>
            )}
            {activeSection === section.key && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400"></div>
            )}
          </button>
        ))}
      </div>

      {/* Section Content */}
      <div>
        {activeSection === 'crypto' && <CryptoArbitrageSection />}
        {activeSection === 'weather' && <WeatherArbitrageSection />}
        {activeSection === 'economic' && (
          <div className="text-center text-gray-500 py-8">
            Economic arbitrage coming soon
          </div>
        )}
      </div>
    </div>
  );
}

export default ArbitrageHub;
