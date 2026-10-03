// ─── ReasoningDisplay ────────────────────────────────────────────────────────
// Reusable reasoning visualization — can be embedded anywhere
import React from 'react';
import type { PlanStep } from '../types';
import PlanStepComponent from '@/components/chat/PlanStep';

interface ReasoningDisplayProps {
  steps: PlanStep[];
  title?: string;
  compact?: boolean;
}

const ReasoningDisplay: React.FC<ReasoningDisplayProps> = ({
  steps,
  title = 'Agent Reasoning',
  compact = false,
}) => {
  if (!steps || steps.length === 0) {
    return (
      <div className="text-neutral-400 text-sm italic py-2">
        No reasoning steps available.
      </div>
    );
  }

  return (
    <div className="reasoning-display">
      {!compact && (
        <h3 className="text-sm font-semibold text-neutral-600 mb-3 flex items-center gap-2">
          <svg className="w-4 h-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          {title}
        </h3>
      )}
      <div className="relative">
        {/* Vertical timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-px bg-primary-100" />
        <div className={`space-y-${compact ? '2' : '3'} pl-2`}>
          {steps.map((step, idx) => (
            <PlanStepComponent
              key={step.step ?? idx}
              step={step}
              isLast={idx === steps.length - 1}
              compact={compact}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default ReasoningDisplay;
