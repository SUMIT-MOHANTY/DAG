// ─── ReasoningPanel ──────────────────────────────────────────────────────────
// Expandable panel showing agent plan steps below an assistant message
import React, { useState } from 'react';
import type { PlanStep } from '@/features/policies/types';
import ReasoningDisplay from '@/features/policies/components/ReasoningDisplay';

interface ReasoningPanelProps {
  steps: PlanStep[];
  defaultOpen?: boolean;
}

const ReasoningPanel: React.FC<ReasoningPanelProps> = ({ steps, defaultOpen = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!steps || steps.length === 0) return null;

  return (
    <div className="mt-2 border border-primary-100 rounded-xl overflow-hidden">
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-primary-50 hover:bg-primary-100 transition-colors text-left group"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-3.5 h-3.5 text-primary-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          <span className="text-xs font-semibold text-primary-700">
            View Reasoning
          </span>
          <span className="text-2xs text-primary-500 bg-primary-100 rounded-full px-1.5 py-0.5">
            {steps.length} step{steps.length !== 1 ? 's' : ''}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-primary-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 py-3 bg-white animate-fade-in">
          <ReasoningDisplay steps={steps} compact={false} />
        </div>
      )}
    </div>
  );
};

export default ReasoningPanel;
