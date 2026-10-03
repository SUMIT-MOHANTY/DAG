// ─── Conflict Handling Hook ──────────────────────────────────────────────────
// Manages optimistic locking conflict detection, version tracking, and retry logic.

import { useState, useCallback, useRef } from 'react';
import type { ConflictState, ApprovalRequest, DecisionPayload } from '../types';
import { approvalsApi } from '../api';

export interface ConflictHandlingState {
  conflict: ConflictState | null;
  isSubmitting: boolean;
  isForceConfirming: boolean;
  error: string | null;
}

export interface UseConflictHandlingReturn extends ConflictHandlingState {
  submitDecision: (
    requestId: string,
    payload: DecisionPayload,
    currentRequest: ApprovalRequest
  ) => Promise<ApprovalRequest | null>;
  handleRefreshAndReview: () => Promise<ApprovalRequest | null>;
  handleForceDecision: () => void;
  confirmForceDecision: () => Promise<ApprovalRequest | null>;
  cancelConflict: () => void;
  clearError: () => void;
}

export function useConflictHandling(): UseConflictHandlingReturn {
  const [conflict, setConflict] = useState<ConflictState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isForceConfirming, setIsForceConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Store the pending payload for retry
  const pendingPayloadRef = useRef<{ requestId: string; payload: DecisionPayload } | null>(null);

  const submitDecision = useCallback(
    async (
      requestId: string,
      payload: DecisionPayload,
      currentRequest: ApprovalRequest
    ): Promise<ApprovalRequest | null> => {
      setIsSubmitting(true);
      setError(null);

      try {
        const result = await approvalsApi.submitDecision(requestId, payload);
        pendingPayloadRef.current = null;
        return result;
      } catch (err: unknown) {
        const axiosErr = err as { response?: { status?: number; data?: { current_status?: string; updated_by?: string; version?: number } } };

        if (axiosErr?.response?.status === 409) {
          // Optimistic locking conflict
          const serverData = axiosErr.response.data;
          const conflictState: ConflictState = {
            requestId,
            localVersion: payload.version,
            serverVersion: serverData?.version ?? payload.version + 1,
            serverStatus: (serverData?.current_status as ConflictState['serverStatus']) ?? 'approved',
            serverUpdatedBy: serverData?.updated_by ?? 'Another user',
            intendedAction: payload.action,
            intendedRationale: payload.rationale,
          };
          setConflict(conflictState);
          pendingPayloadRef.current = { requestId, payload };
          return null;
        }

        const message =
          (err as { message?: string })?.message ?? 'An unexpected error occurred';
        setError(message);
        return null;
      } finally {
        setIsSubmitting(false);
      }
    },
    []
  );

  const handleRefreshAndReview = useCallback(async (): Promise<ApprovalRequest | null> => {
    if (!conflict) return null;
    setIsSubmitting(true);
    try {
      const fresh = await approvalsApi.getById(conflict.requestId);
      setConflict(null);
      pendingPayloadRef.current = null;
      return fresh;
    } catch {
      setError('Failed to refresh request. Please try again.');
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, [conflict]);

  const handleForceDecision = useCallback(() => {
    setIsForceConfirming(true);
  }, []);

  const confirmForceDecision = useCallback(async (): Promise<ApprovalRequest | null> => {
    if (!conflict || !pendingPayloadRef.current) return null;
    setIsSubmitting(true);
    setIsForceConfirming(false);
    try {
      const { requestId, payload } = pendingPayloadRef.current;
      const result = await approvalsApi.submitDecisionForce(requestId, payload);
      setConflict(null);
      pendingPayloadRef.current = null;
      return result;
    } catch (err) {
      const message = (err as { message?: string })?.message ?? 'Force submit failed';
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, [conflict]);

  const cancelConflict = useCallback(() => {
    setConflict(null);
    setIsForceConfirming(false);
    // NOTE: pendingPayloadRef is intentionally kept so the comment draft is preserved
    // The parent component should read back the rationale from the conflict state before clearing
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    conflict,
    isSubmitting,
    isForceConfirming,
    error,
    submitDecision,
    handleRefreshAndReview,
    handleForceDecision,
    confirmForceDecision,
    cancelConflict,
    clearError,
  };
}
