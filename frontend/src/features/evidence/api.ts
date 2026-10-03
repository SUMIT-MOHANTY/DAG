// ─── Evidence & Approvals API Layer ─────────────────────────────────────────
import apiClient from '@/utils/apiClient';
import type {
  ApprovalRequest,
  DecisionPayload,
  AssignPayload,
  EvidenceItem,
  AuditLog,
} from './types';

// ─── Approvals ────────────────────────────────────────────────────────────────

export const approvalsApi = {
  /** Fetch all pending approval requests (queue) */
  getQueue: async (params?: {
    queue_type?: string;
    priority?: string;
    status?: string;
    assigned_to?: string;
  }): Promise<ApprovalRequest[]> => {
    const query = new URLSearchParams();
    if (params?.queue_type && params.queue_type !== 'all') query.set('queue_type', params.queue_type);
    if (params?.priority && params.priority !== 'all') query.set('priority', params.priority);
    if (params?.status && params.status !== 'all') query.set('status', params.status);
    if (params?.assigned_to) query.set('assigned_to', params.assigned_to);

    const qs = query.toString();
    const response = await apiClient.get<ApprovalRequest[]>(
      `/approvals/my-queue${qs ? `?${qs}` : ''}`
    );
    return response.data;
  },

  /** Fetch a single approval request by ID */
  getById: async (requestId: string): Promise<ApprovalRequest> => {
    const response = await apiClient.get<ApprovalRequest>(`/approvals/${requestId}`);
    return response.data;
  },

  /** Submit a decision (approve / reject / escalate / withdraw) */
  submitDecision: async (
    requestId: string,
    payload: DecisionPayload
  ): Promise<ApprovalRequest> => {
    const { action, ...rest } = payload;
    const response = await apiClient.patch<ApprovalRequest>(
      `/approvals/${requestId}/${action}`,
      rest
    );
    return response.data;
  },

  /** Submit a decision with force override (bypasses version check) */
  submitDecisionForce: async (
    requestId: string,
    payload: DecisionPayload
  ): Promise<ApprovalRequest> => {
    const { action, ...rest } = payload;
    const response = await apiClient.patch<ApprovalRequest>(
      `/approvals/${requestId}/${action}`,
      { ...rest, force: true }
    );
    return response.data;
  },

  /** Approve */
  approve: async (requestId: string, rationale: string, version: number) =>
    approvalsApi.submitDecision(requestId, { action: 'approve', rationale, version }),

  /** Reject */
  reject: async (requestId: string, rationale: string, version: number) =>
    approvalsApi.submitDecision(requestId, { action: 'reject', rationale, version }),

  /** Escalate */
  escalate: async (requestId: string, rationale: string, version: number) =>
    approvalsApi.submitDecision(requestId, { action: 'escalate', rationale, version }),

  /** Withdraw */
  withdraw: async (requestId: string, rationale: string, version: number) =>
    approvalsApi.submitDecision(requestId, { action: 'withdraw', rationale, version }),
};

// ─── Evidence ─────────────────────────────────────────────────────────────────

export const evidenceApi = {
  /** Fetch evidence by ID */
  getById: async (evidenceId: string): Promise<EvidenceItem> => {
    const response = await apiClient.get<EvidenceItem>(`/evidence/${evidenceId}`);
    return response.data;
  },

  /** Submit new evidence */
  submit: async (payload: Partial<EvidenceItem>): Promise<EvidenceItem> => {
    const response = await apiClient.post<EvidenceItem>('/evidence', payload);
    return response.data;
  },

  /** Update evidence */
  update: async (evidenceId: string, payload: Partial<EvidenceItem>): Promise<EvidenceItem> => {
    const response = await apiClient.patch<EvidenceItem>(`/evidence/${evidenceId}`, payload);
    return response.data;
  },
};

// ─── Audit ────────────────────────────────────────────────────────────────────

export const auditApi = {
  /** Fetch audit logs with optional filters */
  getLogs: async (params?: {
    search?: string;
    from_date?: string;
    to_date?: string;
    action?: string;
    actor?: string;
    integrity_status?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLog[]> => {
    const query = new URLSearchParams();
    if (params?.search) query.set('search', params.search);
    if (params?.from_date) query.set('from_date', params.from_date);
    if (params?.to_date) query.set('to_date', params.to_date);
    if (params?.action) query.set('action', params.action);
    if (params?.actor) query.set('actor', params.actor);
    if (params?.integrity_status) query.set('integrity_status', params.integrity_status);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    try {
      const response = await apiClient.get<AuditLog[]>(`/audit${qs ? `?${qs}` : ''}`);
      return response.data;
    } catch {
      return mockAuditLogs;
    }
  },

  /** Verify audit chain integrity */
  verifyChain: async (): Promise<{ status: string; tampered_count: number; verified_count: number }> => {
    try {
      const response = await apiClient.get<{ status: string; tampered_count: number; verified_count: number }>('/audit/verify');
      return response.data;
    } catch {
      return { status: 'PARTIAL', tampered_count: 2, verified_count: 10 };
    }
  },

  /** Export audit logs as CSV */
  exportCsv: async (): Promise<Blob> => {
    try {
      const response = await apiClient.get('/audit/export', { responseType: 'blob' });
      return response.data as Blob;
    } catch {
      // Generate mock CSV
      const headers = 'id,timestamp,actor,action,entity_type,entity_id,integrity_status\n';
      const rows = mockAuditLogs
        .map(l => `${l.id},${l.timestamp},${l.actor},${l.action},${l.entity_type},${l.entity_id},${l.integrity_status}`)
        .join('\n');
      return new Blob([headers + rows], { type: 'text/csv' });
    }
  },
};

// ─── Mock Audit Data ──────────────────────────────────────────────────────────

export const mockAuditLogs: AuditLog[] = [
  {
    id: 'AUD-001',
    timestamp: '2024-01-15T08:30:00Z',
    actor: 'Alex Morgan',
    actor_role: 'Risk Manager',
    action: 'APPROVAL_SUBMITTED',
    entity_type: 'ApprovalRequest',
    entity_id: 'APR-2024-001',
    payload_hash: 'a1b2c3d4e5f6789012345678901234567890abcd',
    previous_hash: null,
    verification_timestamp: '2024-01-15T08:30:01Z',
    integrity_status: 'VERIFIED',
    details: { action: 'approve', rationale: 'Documents verified', version: 1 },
  },
  {
    id: 'AUD-002',
    timestamp: '2024-01-15T09:15:00Z',
    actor: 'Sarah Chen',
    actor_role: 'Risk Manager',
    action: 'APPROVAL_REJECTED',
    entity_type: 'ApprovalRequest',
    entity_id: 'APR-2024-002',
    payload_hash: 'b2c3d4e5f6789012345678901234567890abcde1',
    previous_hash: 'a1b2c3d4e5f6789012345678901234567890abcd',
    verification_timestamp: '2024-01-15T09:15:01Z',
    integrity_status: 'VERIFIED',
    details: { action: 'reject', rationale: 'Visa not confirmed', version: 2 },
  },
  {
    id: 'AUD-003',
    timestamp: '2024-01-15T09:45:00Z',
    actor: 'David Okafor',
    actor_role: 'Risk Analyst',
    action: 'EVIDENCE_UPLOADED',
    entity_type: 'Evidence',
    entity_id: 'EV-003-A',
    payload_hash: 'c3d4e5f6789012345678901234567890abcdef12',
    previous_hash: 'b2c3d4e5f6789012345678901234567890abcde1',
    verification_timestamp: '2024-01-15T09:45:01Z',
    integrity_status: 'VERIFIED',
    details: { source: 'IATA', confidence: 0.92 },
  },
  {
    id: 'AUD-004',
    timestamp: '2024-01-15T10:00:00Z',
    actor: 'System',
    actor_role: 'Automation',
    action: 'AUTO_ESCALATION',
    entity_type: 'ApprovalRequest',
    entity_id: 'APR-2024-003',
    payload_hash: 'd4e5f6789012345678901234567890abcdef1234',
    previous_hash: 'c3d4e5f6789012345678901234567890abcdef12',
    verification_timestamp: '2024-01-15T10:00:01Z',
    integrity_status: 'VERIFIED',
    details: { reason: 'Timeout exceeded 30 minutes', escalated_to: 'Senior Manager' },
  },
  {
    id: 'AUD-005',
    timestamp: '2024-01-15T10:30:00Z',
    actor: 'Admin User',
    actor_role: 'Administrator',
    action: 'CONFIG_UPDATED',
    entity_type: 'SystemConfig',
    entity_id: 'CONFIG-001',
    payload_hash: 'e5f6789012345678901234567890abcdef123456',
    previous_hash: 'd4e5f6789012345678901234567890abcdef1234',
    verification_timestamp: '2024-01-15T10:30:01Z',
    integrity_status: 'VERIFIED',
    details: { high_risk_threshold: 7, low_confidence_threshold: 0.7 },
  },
  {
    id: 'AUD-006',
    timestamp: '2024-01-15T11:00:00Z',
    actor: 'Alex Morgan',
    actor_role: 'Risk Manager',
    action: 'APPROVAL_ESCALATED',
    entity_type: 'ApprovalRequest',
    entity_id: 'APR-2024-004',
    payload_hash: 'f6789012345678901234567890abcdef12345678',
    previous_hash: 'e5f6789012345678901234567890abcdef123456',
    verification_timestamp: '2024-01-15T11:00:01Z',
    integrity_status: 'VERIFIED',
    details: { action: 'escalate', rationale: 'Requires senior review' },
  },
  {
    id: 'AUD-007',
    timestamp: '2024-01-15T11:30:00Z',
    actor: 'Unknown',
    actor_role: 'Unknown',
    action: 'RECORD_MODIFIED',
    entity_type: 'ApprovalRequest',
    entity_id: 'APR-2024-005',
    payload_hash: '0000000000000000000000000000000000000000',
    previous_hash: 'f6789012345678901234567890abcdef12345678',
    verification_timestamp: '2024-01-15T11:30:01Z',
    integrity_status: 'FAILED',
    details: { error: 'Hash mismatch detected — record may have been tampered with' },
  },
  {
    id: 'AUD-008',
    timestamp: '2024-01-15T12:00:00Z',
    actor: 'Sarah Chen',
    actor_role: 'Risk Manager',
    action: 'APPROVAL_APPROVED',
    entity_type: 'ApprovalRequest',
    entity_id: 'APR-2024-006',
    payload_hash: '789012345678901234567890abcdef1234567890',
    previous_hash: '0000000000000000000000000000000000000000',
    verification_timestamp: '2024-01-15T12:00:01Z',
    integrity_status: 'VERIFIED',
    details: { action: 'approve', rationale: 'All documents verified', version: 3 },
  },
  {
    id: 'AUD-009',
    timestamp: '2024-01-15T12:30:00Z',
    actor: 'David Okafor',
    actor_role: 'Risk Analyst',
    action: 'EVIDENCE_VERIFIED',
    entity_type: 'Evidence',
    entity_id: 'EV-006-A',
    payload_hash: '89012345678901234567890abcdef123456789012',
    previous_hash: '789012345678901234567890abcdef1234567890',
    verification_timestamp: '2024-01-15T12:30:01Z',
    integrity_status: 'VERIFIED',
    details: { verified_by: 'David Okafor', confidence_updated: 0.91 },
  },
  {
    id: 'AUD-010',
    timestamp: '2024-01-15T13:00:00Z',
    actor: 'System',
    actor_role: 'Automation',
    action: 'RESEED_EXECUTED',
    entity_type: 'Database',
    entity_id: 'DB-001',
    payload_hash: '9012345678901234567890abcdef12345678901234',
    previous_hash: '89012345678901234567890abcdef123456789012',
    verification_timestamp: '2024-01-15T13:00:01Z',
    integrity_status: 'VERIFIED',
    details: { records_seeded: 42, duration_ms: 1240 },
  },
  {
    id: 'AUD-011',
    timestamp: '2024-01-15T13:30:00Z',
    actor: 'Unknown',
    actor_role: 'Unknown',
    action: 'UNAUTHORIZED_ACCESS',
    entity_type: 'SystemConfig',
    entity_id: 'CONFIG-001',
    payload_hash: '1111111111111111111111111111111111111111',
    previous_hash: '9012345678901234567890abcdef12345678901234',
    verification_timestamp: '2024-01-15T13:30:01Z',
    integrity_status: 'FAILED',
    details: { error: 'Unauthorized config modification detected — chain integrity broken' },
  },
  {
    id: 'AUD-012',
    timestamp: '2024-01-15T14:00:00Z',
    actor: 'Admin User',
    actor_role: 'Administrator',
    action: 'AUDIT_EXPORTED',
    entity_type: 'AuditLog',
    entity_id: 'EXPORT-001',
    payload_hash: '012345678901234567890abcdef1234567890123456',
    previous_hash: '1111111111111111111111111111111111111111',
    verification_timestamp: '2024-01-15T14:00:01Z',
    integrity_status: 'VERIFIED',
    details: { exported_by: 'Admin User', record_count: 11 },
  },
];
