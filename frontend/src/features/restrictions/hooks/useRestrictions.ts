// ─── Restrictions Data Hook ──────────────────────────────────────────────────
import { useCallback, useEffect, useRef, useState } from 'react';
import { restrictionsApi } from '../api';
import type {
  CursorPage,
  RestrictionCreate,
  RestrictionFilters,
  RestrictionResponse,
  RestrictionUpdate,
} from '../types';

// ── List hook ────────────────────────────────────────────────────────────────
export function useRestrictions(filters: RestrictionFilters) {
  const [data, setData]       = useState<CursorPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const abortRef              = useRef<AbortController | null>(null);

  const fetch = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setLoading(true);
    setError(null);
    try {
      const result = await restrictionsApi.list(filters);
      setData(result);
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message ?? 'Failed to load restrictions');
      }
    } finally {
      setLoading(false);
    }
  }, [JSON.stringify(filters)]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch();
    return () => abortRef.current?.abort();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// ── Single restriction hook ───────────────────────────────────────────────────
export function useRestriction(id: string | null) {
  const [data, setData]       = useState<RestrictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    restrictionsApi
      .get(id)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  return { data, loading, error };
}

// ── Mutation hooks ────────────────────────────────────────────────────────────
export function useCreateRestriction() {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const create = useCallback(async (payload: RestrictionCreate): Promise<RestrictionResponse | null> => {
    setLoading(true);
    setError(null);
    try {
      return await restrictionsApi.create(payload);
    } catch (err: unknown) {
      setError((err as Error).message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { create, loading, error };
}

export function useUpdateRestriction() {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const update = useCallback(
    async (id: string, payload: RestrictionUpdate): Promise<RestrictionResponse | null> => {
      setLoading(true);
      setError(null);
      try {
        return await restrictionsApi.update(id, payload);
      } catch (err: unknown) {
        setError((err as Error).message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { update, loading, error };
}
