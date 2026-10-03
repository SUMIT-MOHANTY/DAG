// ─── Audit Trail Hook ────────────────────────────────────────────────────────
// Manages audit log fetching, filtering, chain verification, and CSV export.

import { useState, useCallback, useEffect } from 'react';
import type { AuditLog, IntegrityStatus } from '../types';
import { auditApi, mockAuditLogs } from '../api';

export interface AuditFilters {
  search: string;
  action: string;
  actor: string;
  integrity_status: IntegrityStatus | 'all';
  from_date: string;
  to_date: string;
}

export const defaultAuditFilters: AuditFilters = {
  search: '',
  action: '',
  actor: '',
  integrity_status: 'all',
  from_date: '',
  to_date: '',
};

export interface VerifyResult {
  status: string;
  tampered_count: number;
  verified_count: number;
}

export interface UseAuditReturn {
  logs: AuditLog[];
  filteredLogs: AuditLog[];
  isLoading: boolean;
  isVerifying: boolean;
  isExporting: boolean;
  verifyResult: VerifyResult | null;
  filters: AuditFilters;
  highlightedIds: Set<string>;
  error: string | null;
  setFilters: (filters: Partial<AuditFilters>) => void;
  resetFilters: () => void;
  verifyChain: () => Promise<void>;
  exportCsv: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useAudit(): UseAuditReturn {
  const [logs, setLogs] = useState<AuditLog[]>(mockAuditLogs);
  const [isLoading, setIsLoading] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [filters, setFiltersState] = useState<AuditFilters>(defaultAuditFilters);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditApi.getLogs({
        search: filters.search || undefined,
        action: filters.action || undefined,
        actor: filters.actor || undefined,
        integrity_status: filters.integrity_status !== 'all' ? filters.integrity_status : undefined,
        from_date: filters.from_date || undefined,
        to_date: filters.to_date || undefined,
      });
      setLogs(data);
    } catch {
      setError('Failed to load audit logs');
      setLogs(mockAuditLogs);
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Client-side filtering on top of server data
  const filteredLogs = logs.filter((log) => {
    const searchLower = filters.search.toLowerCase();
    if (
      filters.search &&
      !log.actor.toLowerCase().includes(searchLower) &&
      !log.action.toLowerCase().includes(searchLower) &&
      !log.entity_type.toLowerCase().includes(searchLower) &&
      !log.entity_id.toLowerCase().includes(searchLower)
    ) {
      return false;
    }
    if (filters.integrity_status !== 'all' && log.integrity_status !== filters.integrity_status) {
      return false;
    }
    if (filters.action && !log.action.toLowerCase().includes(filters.action.toLowerCase())) {
      return false;
    }
    if (filters.actor && !log.actor.toLowerCase().includes(filters.actor.toLowerCase())) {
      return false;
    }
    return true;
  });

  const setFilters = useCallback((partial: Partial<AuditFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...partial }));
  }, []);

  const resetFilters = useCallback(() => {
    setFiltersState(defaultAuditFilters);
  }, []);

  const verifyChain = useCallback(async () => {
    setIsVerifying(true);
    setError(null);
    try {
      const result = await auditApi.verifyChain();
      setVerifyResult(result);
      // Highlight tampered records
      const tampered = new Set(
        logs
          .filter((l) => l.integrity_status === 'FAILED')
          .map((l) => l.id)
      );
      setHighlightedIds(tampered);
    } catch {
      setError('Chain verification failed');
    } finally {
      setIsVerifying(false);
    }
  }, [logs]);

  const exportCsv = useCallback(async () => {
    setIsExporting(true);
    try {
      const blob = await auditApi.exportCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.href = url;
      a.download = `audit-export-${ts}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setError('Export failed');
    } finally {
      setIsExporting(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    await fetchLogs();
  }, [fetchLogs]);

  return {
    logs,
    filteredLogs,
    isLoading,
    isVerifying,
    isExporting,
    verifyResult,
    filters,
    highlightedIds,
    error,
    setFilters,
    resetFilters,
    verifyChain,
    exportCsv,
    refresh,
  };
}
