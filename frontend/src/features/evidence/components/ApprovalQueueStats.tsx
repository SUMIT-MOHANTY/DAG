// ─── Approval Queue Stats Cards ──────────────────────────────────────────────
import React from 'react';
import type { QueueStats, ApprovalFiltersState } from '../types';

interface Props {
  stats: QueueStats;
  onFilterShortcut: (partial: Partial<ApprovalFiltersState>) => void;
}

interface StatCard {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
  bg: string;
  border: string;
  filter: Partial<ApprovalFiltersState>;
}

export const ApprovalQueueStats: React.FC<Props> = ({ stats, onFilterShortcut }) => {
  const cards: StatCard[] = [
    {
      label: 'High Risk',
      value: stats.highRisk,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
      color: 'text-danger-600',
      bg: 'bg-danger-50',
      border: 'border-danger-200 hover:border-danger-400',
      filter: { queueType: 'high_risk', status: 'all' },
    },
    {
      label: 'Low Confidence',
      value: stats.lowConfidence,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: 'text-warning-600',
      bg: 'bg-warning-50',
      border: 'border-warning-200 hover:border-warning-400',
      filter: { queueType: 'low_confidence', status: 'all' },
    },
    {
      label: 'Urgent',
      value: stats.urgent,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      color: 'text-primary-600',
      bg: 'bg-primary-50',
      border: 'border-primary-200 hover:border-primary-400',
      filter: { priority: 'urgent', status: 'all' },
    },
    {
      label: 'In Review',
      value: stats.inReview,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      ),
      color: 'text-success-600',
      bg: 'bg-success-50',
      border: 'border-success-200 hover:border-success-400',
      filter: { status: 'in_review' },
    },
    {
      label: 'Total Queue',
      value: stats.total,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
      ),
      color: 'text-neutral-600',
      bg: 'bg-neutral-50',
      border: 'border-neutral-200 hover:border-neutral-400',
      filter: { queueType: 'all', priority: 'all', status: 'all' },
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
      {cards.map((card) => (
        <button
          key={card.label}
          onClick={() => onFilterShortcut(card.filter)}
          className={`
            flex items-center gap-3 p-4 rounded-xl border-2 transition-all duration-150
            ${card.bg} ${card.border} cursor-pointer text-left
            hover:shadow-soft active:scale-95
          `}
        >
          <div className={`flex-shrink-0 ${card.color}`}>{card.icon}</div>
          <div>
            <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
            <div className="text-xs font-medium text-neutral-500 leading-tight">{card.label}</div>
          </div>
        </button>
      ))}
    </div>
  );
};

export default ApprovalQueueStats;
