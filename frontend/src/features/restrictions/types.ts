// ─── Restriction Domain Types ────────────────────────────────────────────────

export type RiskLevel = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10;

export interface EvidenceSummary {
  id: string;
  source_table: string;
  source_record_id: string;
  confidence_score: number | null;
  collected_at: string;
}

export interface RestrictionListItem {
  id: string;
  name: string;
  rule_type: string;
  risk_level: RiskLevel;
  is_active: boolean;
  effective_from: string;
  effective_to: string | null;
  source_policy_id: string | null;
  created_at: string;
  relevance_score?: number | null;
}

export interface RestrictionResponse {
  id: string;
  name: string;
  description: string | null;
  rule_type: string;
  parameters: Record<string, unknown> | null;
  risk_level: RiskLevel;
  source_policy_id: string | null;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  evidence_items: EvidenceSummary[];
}

export interface RestrictionCreate {
  name: string;
  description?: string;
  rule_type: string;
  parameters?: Record<string, unknown>;
  risk_level: RiskLevel;
  source_policy_id?: string;
  effective_from: string;
  effective_to?: string;
}

export interface RestrictionUpdate {
  name?: string;
  description?: string;
  rule_type?: string;
  parameters?: Record<string, unknown>;
  risk_level?: RiskLevel;
  source_policy_id?: string;
  effective_from?: string;
  effective_to?: string;
}

export interface CursorPage {
  items: RestrictionListItem[];
  next_cursor: string | null;
  prev_cursor: string | null;
  total_count: number | null;
  page_size: number;
}

export interface RestrictionFilters {
  risk_level?: number;
  risk_levels?: number[];
  is_active?: boolean;
  effective_from_gte?: string;
  effective_from_lte?: string;
  policy_id?: string;
  search?: string;
  cursor?: string;
  page_size?: number;
}

export const RISK_LEVEL_LABELS: Record<number, string> = {
  1: 'Minimal',
  2: 'Very Low',
  3: 'Low',
  4: 'Moderate',
  5: 'Medium',
  6: 'Elevated',
  7: 'High',
  8: 'Very High',
  9: 'Critical',
  10: 'Extreme',
};

export const RISK_LEVEL_COLORS: Record<number, { bg: string; text: string; border: string }> = {
  1:  { bg: 'bg-emerald-50',  text: 'text-emerald-700',  border: 'border-emerald-200' },
  2:  { bg: 'bg-emerald-50',  text: 'text-emerald-700',  border: 'border-emerald-200' },
  3:  { bg: 'bg-green-50',    text: 'text-green-700',    border: 'border-green-200'   },
  4:  { bg: 'bg-yellow-50',   text: 'text-yellow-700',   border: 'border-yellow-200'  },
  5:  { bg: 'bg-amber-50',    text: 'text-amber-700',    border: 'border-amber-200'   },
  6:  { bg: 'bg-orange-50',   text: 'text-orange-700',   border: 'border-orange-200'  },
  7:  { bg: 'bg-red-50',      text: 'text-red-700',      border: 'border-red-200'     },
  8:  { bg: 'bg-red-100',     text: 'text-red-800',      border: 'border-red-300'     },
  9:  { bg: 'bg-rose-100',    text: 'text-rose-800',     border: 'border-rose-300'    },
  10: { bg: 'bg-rose-200',    text: 'text-rose-900',     border: 'border-rose-400'    },
};
