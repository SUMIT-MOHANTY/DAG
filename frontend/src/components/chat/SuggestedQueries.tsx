// ─── SuggestedQueries ────────────────────────────────────────────────────────
import React from 'react';

interface SuggestedQueriesProps {
  onSelect: (query: string) => void;
}

const SUGGESTIONS = [
  {
    icon: '👨‍👩‍👧',
    label: 'Family booking restrictions',
    query: 'What restrictions apply to family bookings with children?',
  },
  {
    icon: '⚠️',
    label: 'High-risk properties',
    query: 'Show me high-risk properties and their current restrictions',
  },
  {
    icon: '📋',
    label: 'Policy overview',
    query: 'Give me an overview of all active booking policies',
  },
  {
    icon: '🔍',
    label: 'Age-specific rules',
    query: 'What age-specific rules apply to guests under 18?',
  },
  {
    icon: '🏨',
    label: 'Room type limits',
    query: 'Are there occupancy limits for suite room types?',
  },
  {
    icon: '📅',
    label: 'Seasonal restrictions',
    query: 'What seasonal restrictions are active for the next 30 days?',
  },
];

const SuggestedQueries: React.FC<SuggestedQueriesProps> = ({ onSelect }) => {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-12 animate-fade-in">
      {/* Hero */}
      <div className="mb-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center mx-auto mb-4 shadow-soft">
          <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-neutral-800 mb-2">Ask About Restrictions</h2>
        <p className="text-sm text-neutral-500 max-w-sm">
          Query booking policies, evaluate restrictions, and get explainable AI-powered answers.
        </p>
      </div>

      {/* Suggestion grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full max-w-2xl">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.query}
            onClick={() => onSelect(s.query)}
            className="group flex items-start gap-3 p-3.5 rounded-xl border border-neutral-200 bg-white hover:border-primary-300 hover:bg-primary-50 hover:shadow-soft transition-all duration-150 text-left"
          >
            <span className="text-xl flex-shrink-0 mt-0.5">{s.icon}</span>
            <div>
              <p className="text-xs font-semibold text-neutral-700 group-hover:text-primary-700 mb-0.5">
                {s.label}
              </p>
              <p className="text-2xs text-neutral-400 leading-relaxed line-clamp-2">{s.query}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default SuggestedQueries;
