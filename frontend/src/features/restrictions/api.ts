// ─── Restrictions API Client ─────────────────────────────────────────────────
import type {
  CursorPage,
  RestrictionCreate,
  RestrictionFilters,
  RestrictionResponse,
  RestrictionUpdate,
} from './types';

const BASE = '/api/v1/restrictions';

function buildQuery(filters: RestrictionFilters): string {
  const params = new URLSearchParams();
  if (filters.risk_level != null)       params.set('risk_level', String(filters.risk_level));
  if (filters.is_active != null)        params.set('is_active', String(filters.is_active));
  if (filters.effective_from_gte)       params.set('effective_from_gte', filters.effective_from_gte);
  if (filters.effective_from_lte)       params.set('effective_from_lte', filters.effective_from_lte);
  if (filters.policy_id)                params.set('policy_id', filters.policy_id);
  if (filters.search)                   params.set('search', filters.search);
  if (filters.cursor)                   params.set('cursor', filters.cursor);
  if (filters.page_size != null)        params.set('page_size', String(filters.page_size));
  return params.toString() ? `?${params.toString()}` : '';
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const restrictionsApi = {
  list: (filters: RestrictionFilters = {}): Promise<CursorPage> =>
    fetch(`${BASE}${buildQuery(filters)}`, { headers: authHeaders() }).then(handleResponse),

  get: (id: string): Promise<RestrictionResponse> =>
    fetch(`${BASE}/${id}`, { headers: authHeaders() }).then(handleResponse),

  create: (payload: RestrictionCreate): Promise<RestrictionResponse> =>
    fetch(BASE, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    }).then(handleResponse),

  update: (id: string, payload: RestrictionUpdate): Promise<RestrictionResponse> =>
    fetch(`${BASE}/${id}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    }).then(handleResponse),

  delete: (id: string): Promise<void> =>
    fetch(`${BASE}/${id}`, { method: 'DELETE', headers: authHeaders() }).then(handleResponse),
};
