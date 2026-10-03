// ─── Approval Filters Bar ────────────────────────────────────────────────────
import React from 'react';
import type { ApprovalFiltersState, QueueType, Priority, ApprovalStatus } from '../types';

interface Props {
  filters: ApprovalFiltersState;
  onChange: (filters: ApprovalFiltersState) => void;
  onRefresh: () => void;
  loading: boolean;
}

export const ApprovalFilters: React.FC<Props> = ({ filters, onChange, onRefresh, loading }) => {
  const update = <K extends keyof ApprovalFiltersState>(key: K, value: ApprovalFiltersState[K]) => {
    onChange({ ...filters, [key]: value });
  };

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px]">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400"
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          placeholder="Search by Request ID…"
          value={filters.search}
          onChange={e => update('search', e.target.value)}
          className="
            w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-neutral-200
            bg-white text-neutral-800 placeholder-neutral-400
            focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400
            transition-colors
          "
        />
      </div>

      {/* Queue Type */}
      <select
        value={filters.queueType}
        onChange={e => update('queueType', e.target.value as QueueType | 'all')}
        className="
          px-3 py-2 text-sm rounded-lg border border-neutral-200 bg-white
          text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-300
          focus:border-primary-400 transition-colors cursor-pointer
        "
      >
        <option value="all">All Queue Types</option>
        <option value="high_risk">High Risk</option>
        <option value="low_confidence">Low Confidence</option>
      </select>

      {/* Priority */}
      <select
        value={filters.priority}
        onChange={e => update('priority', e.target.value as Priority | 'all')}
        className="
          px-3 py-2 text-sm rounded-lg border border-neutral-200 bg-white
          text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-300
          focus:border-primary-400 transition-colors cursor-pointer
        "
      >
        <option value="all">All Priorities</option>
        <option value="urgent">Urgent</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>

      {/* Assigned Status */}
      <select
        value={filters.assignedStatus}
        onChange={e => update('assignedStatus', e.target.value as 'all' | 'assigned' | 'unassigned')}
        className="
          px-3 py-2 text-sm rounded-lg border border-neutral-200 bg-white
          text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-300
          focus:border-primary-400 transition-colors cursor-pointer
        "
      >
        <option value="all">All Assignments</option>
        <option value="unassigned">Unassigned</option>
        <option value="assigned">Assigned</option>
      </select>

      {/* Status */}
      <select
        value={filters.status}
        onChange={e => update('status', e.target.value as ApprovalStatus | 'all')}
        className="
          px-3 py-2 text-sm rounded-lg border border-neutral-200 bg-white
          text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-300
          focus:border-primary-400 transition-colors cursor-pointer
        "
      >
        <option value="all">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="in_review">In Review</option>
        <option value="approved">Approved</option>
        <option value="rejected">Rejected</option>
        <option value="escalated">Escalated</option>
      </select>

      {/* Refresh */}
      <button
        onClick={onRefresh}
        disabled={loading}
        className="
          flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
          bg-white border border-neutral-200 text-neutral-600
          hover:bg-neutral-50 hover:border-neutral-300
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-all duration-150 active:scale-95
        "
      >
        <svg
          className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Refresh
      </button>
    </div>
  );
};

export default ApprovalFilters;
