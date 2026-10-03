// ─── PlanStep ─────────────────────────────────────────────────────────────────
import React from 'react';
import type { PlanStep as PlanStepType } from '@/features/policies/types';

interface PlanStepProps {
  step: PlanStepType;
  isLast?: boolean;
  compact?: boolean;
}

const ACTION_ICONS: Record<string, string> = {
  search_restrictions: '🔍',
  retrieve_candidates: '📋',
  evaluate_context: '⚖️',
  generate_answer: '✨',
  check_approval: '🔐',
  fetch_property: '🏨',
  default: '⚙️',
};

const STATUS_COLORS = {
  pending: 'bg-neutral-200 text-neutral-500',
  running: 'bg-primary-100 text-primary-600 animate-pulse',
  done: 'bg-success-100 text-success-700',
  error: 'bg-danger-100 text-danger-700',
};

const PlanStep: React.FC<PlanStepProps> = ({ step, isLast = false, compact = false }) => {
  const icon = ACTION_ICONS[step.action] ?? ACTION_ICONS.default;
  const status = step.status ?? 'done';
  const statusColor = STATUS_COLORS[status];

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return ts;
    }
  };

  const formatAction = (action: string) =>
    action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className={`relative flex gap-3 ${compact ? 'pb-2' : 'pb-4'}`}>
      {/* Step dot */}
      <div className="relative z-10 flex-shrink-0">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 border-white shadow-sm ${statusColor}`}
        >
          {status === 'running' ? (
            <span className="inline-block w-3 h-3 rounded-full bg-primary-500 animate-ping" />
          ) : (
            <span>{icon}</span>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">
              Step {step.step}
            </span>
            <p className={`font-medium text-neutral-800 ${compact ? 'text-xs' : 'text-sm'} mt-0.5`}>
              {formatAction(step.action)}
            </p>
          </div>
          {step.timestamp && (
            <span className="text-2xs text-neutral-400 flex-shrink-0 mt-1">
              {formatTime(step.timestamp)}
            </span>
          )}
        </div>

        {!compact && (
          <div className="mt-1.5 space-y-1">
            {step.input && (
              <div className="flex gap-1.5 items-start">
                <span className="text-2xs font-medium text-neutral-400 uppercase tracking-wide mt-0.5 w-10 flex-shrink-0">In</span>
                <span className="text-xs text-neutral-600 bg-neutral-50 rounded px-2 py-0.5 font-mono">
                  {step.input}
                </span>
              </div>
            )}
            {step.output && (
              <div className="flex gap-1.5 items-start">
                <span className="text-2xs font-medium text-neutral-400 uppercase tracking-wide mt-0.5 w-10 flex-shrink-0">Out</span>
                <span className="text-xs text-success-700 bg-success-50 rounded px-2 py-0.5 font-mono">
                  {step.output}
                </span>
              </div>
            )}
            {step.duration_ms !== undefined && (
              <div className="flex gap-1.5 items-center">
                <span className="text-2xs font-medium text-neutral-400 uppercase tracking-wide w-10 flex-shrink-0">Time</span>
                <span className="text-2xs text-neutral-500">{step.duration_ms}ms</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PlanStep;
