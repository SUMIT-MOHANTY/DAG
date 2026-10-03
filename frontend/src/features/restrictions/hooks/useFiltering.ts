// ─── Filter State Management Hook ────────────────────────────────────────────
import { useCallback, useState } from 'react';
import type { RestrictionFilters } from '../types';

const DEFAULT_FILTERS: RestrictionFilters = {
  page_size: 20,
};

export function useFiltering() {
  const [filters, setFilters] = useState<RestrictionFilters>(DEFAULT_FILTERS);

  const updateFilter = useCallback(
    <K extends keyof RestrictionFilters>(key: K, value: RestrictionFilters[K]) => {
      setFilters(prev => ({ ...prev, [key]: value, cursor: undefined }));
    },
    [],
  );

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const setSearch = useCallback((search: string) => {
    setFilters(prev => ({ ...prev, search: search || undefined, cursor: undefined }));
  }, []);

  const setRiskLevel = useCallback((risk_level: number | undefined) => {
    setFilters(prev => ({ ...prev, risk_level, cursor: undefined }));
  }, []);

  const setIsActive = useCallback((is_active: boolean | undefined) => {
    setFilters(prev => ({ ...prev, is_active, cursor: undefined }));
  }, []);

  const setDateRange = useCallback(
    (from: string | undefined, to: string | undefined) => {
      setFilters(prev => ({
        ...prev,
        effective_from_gte: from,
        effective_from_lte: to,
        cursor: undefined,
      }));
    },
    [],
  );

  const setPolicyId = useCallback((policy_id: string | undefined) => {
    setFilters(prev => ({ ...prev, policy_id, cursor: undefined }));
  }, []);

  const nextPage = useCallback((cursor: string) => {
    setFilters(prev => ({ ...prev, cursor }));
  }, []);

  const prevPage = useCallback((cursor: string) => {
    setFilters(prev => ({ ...prev, cursor }));
  }, []);

  const hasActiveFilters =
    !!filters.search ||
    filters.risk_level != null ||
    filters.is_active != null ||
    !!filters.effective_from_gte ||
    !!filters.effective_from_lte ||
    !!filters.policy_id;

  return {
    filters,
    updateFilter,
    resetFilters,
    setSearch,
    setRiskLevel,
    setIsActive,
    setDateRange,
    setPolicyId,
    nextPage,
    prevPage,
    hasActiveFilters,
  };
}
