// ─── useEvidence Hook ────────────────────────────────────────────────────────
import { useState, useCallback, useRef } from 'react';
import { approvalsApi } from '../api';
import type {
  ApprovalRequest,
  ApprovalFiltersState,
  QueueStats,
  DecisionPayload,
} from '../types';
import { mockApprovalRequests } from '@/stores/mockData';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function computeStats(requests: ApprovalRequest[]): QueueStats {
  return {
    highRisk: requests.filter(r => r.queue_type === 'high_risk' && r.status === 'pending').length,
    lowConfidence: requests.filter(r => r.queue_type === 'low_confidence' && r.status === 'pending').length,
    urgent: requests.filter(r => r.priority === 'urgent').length,
    total: requests.length,
    inReview: requests.filter(r => r.status === 'in_review').length,
  };
}

function applyFilters(
  requests: ApprovalRequest[],
  filters: ApprovalFiltersState
): ApprovalRequest[] {
  return requests.filter(r => {
    if (filters.search && !r.id.toLowerCase().includes(filters.search.toLowerCase())) return false;
    if (filters.queueType !== 'all' && r.queue_type !== filters.queueType) return false;
    if (filters.priority !== 'all' && r.priority !== filters.priority) return false;
    if (filters.assignedStatus === 'assigned' && !r.assigned_to) return false;
    if (filters.assignedStatus === 'unassigned' && r.assigned_to) return false;
    if (filters.status !== 'all' && r.status !== filters.status) return false;
    return true;
  });
}

// ─── Default Filters ──────────────────────────────────────────────────────────

export const defaultFilters: ApprovalFiltersState = {
  search: '',
  queueType: 'all',
  priority: 'all',
  assignedStatus: 'all',
  status: 'all',
};

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useApprovalQueue() {
  const [allRequests, setAllRequests] = useState<ApprovalRequest[]>(mockApprovalRequests);
  const [filters, setFilters] = useState<ApprovalFiltersState>(defaultFilters);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filteredRequests = applyFilters(allRequests, filters);
  const stats = computeStats(allRequests);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await approvalsApi.getQueue();
      setAllRequests(data);
    } catch {
      // Fall back to mock data silently
      setAllRequests(mockApprovalRequests);
    } finally {
      setLoading(false);
    }
  }, []);

  const assignToMe = useCallback(
    async (requestId: string, userId: string, userName: string) => {
      // Optimistic update
      setAllRequests(prev =>
        prev.map(r =>
          r.id === requestId
            ? { ...r, assigned_to: userId, assigned_to_name: userName, status: 'in_review' as const }
            : r
        )
      );
    },
    []
  );

  const updateRequest = useCallback((updated: ApprovalRequest) => {
    setAllRequests(prev => prev.map(r => (r.id === updated.id ? updated : r)));
  }, []);

  return {
    requests: filteredRequests,
    allRequests,
    stats,
    filters,
    setFilters,
    loading,
    error,
    refresh,
    assignToMe,
    updateRequest,
  };
}

// ─── Single Approval Detail Hook ──────────────────────────────────────────────

export function useApprovalDetail(requestId: string) {
  const [request, setRequest] = useState<ApprovalRequest | null>(
    mockApprovalRequests.find(r => r.id === requestId) ?? null
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await approvalsApi.getById(requestId);
      setRequest(data);
    } catch {
      const mock = mockApprovalRequests.find(r => r.id === requestId);
      if (mock) setRequest(mock);
      else setError('Approval request not found.');
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  const submitDecision = useCallback(
    async (payload: DecisionPayload): Promise<ApprovalRequest | null> => {
      if (!request) return null;
      setConflictError(false);
      setLoading(true);
      try {
        const updated = await approvalsApi.submitDecision(requestId, payload);
        setRequest(updated);
        return updated;
      } catch (err: any) {
        if (err?.response?.status === 409) {
          setConflictError(true);
          // Re-fetch to get latest version
          await fetch();
        } else {
          // Optimistic mock update for prototype
          const mockUpdated: ApprovalRequest = {
            ...request,
            status: payload.action === 'approve'
              ? 'approved'
              : payload.action === 'reject'
              ? 'rejected'
              : payload.action === 'escalate'
              ? 'escalated'
              : 'withdrawn',
            version: request.version + 1,
            decision_history: [
              ...request.decision_history,
              {
                id: `dh-${Date.now()}`,
                action: payload.action,
                actor: 'current-user',
                actor_role: 'Risk Manager',
                rationale: payload.rationale,
                timestamp: new Date().toISOString(),
                previous_status: request.status,
                new_status: payload.action === 'approve'
                  ? 'approved'
                  : payload.action === 'reject'
                  ? 'rejected'
                  : payload.action === 'escalate'
                  ? 'escalated'
                  : 'withdrawn',
              },
            ],
          };
          setRequest(mockUpdated);
          return mockUpdated;
        }
        return null;
      } finally {
        setLoading(false);
      }
    },
    [request, requestId, fetch]
  );

  return {
    request,
    loading,
    error,
    conflictError,
    fetch,
    submitDecision,
  };
}
