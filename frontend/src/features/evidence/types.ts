// ─── Evidence & Approval Domain Types ───────────────────────────────────────

export type QueueType = 'high_risk' | 'low_confidence';
export type Priority = 'urgent' | 'high' | 'medium' | 'low';
export type ApprovalStatus = 'pending' | 'in_review' | 'approved' | 'rejected' | 'escalated' | 'withdrawn';
export type DecisionAction = 'approve' | 'reject' | 'escalate' | 'withdraw' | 'assign';
export type IntegrityStatus = 'VERIFIED' | 'FAILED' | 'PENDING';

// ─── Evidence ────────────────────────────────────────────────────────────────

export interface EvidenceItem {
  id: string;
  evidence_id: string;
  restriction_name: string;
  restriction_id: string;
  source: string;
  source_url?: string;
  source_type: 'regulatory' | 'policy' | 'contractual' | 'operational';
  confidence: number;
  content: string;
  extracted_at: string;
  verified: boolean;
}

// ─── Booking Context ─────────────────────────────────────────────────────────

export interface BookingContext {
  booking_id: string;
  customer_id: string;
  customer_name: string;
  route: string;
  departure: string;
  destination: string;
  travel_date: string;
  booking_class: string;
  fare_basis: string;
  conversation_id?: string;
}

// ─── Risk Factor ─────────────────────────────────────────────────────────────

export interface RiskFactor {
  factor: string;
  score: number;
  weight: number;
  description: string;
}

export interface RiskAssessment {
  overall_score: number;
  factors: RiskFactor[];
  recommendation: string;
  assessed_at: string;
}

// ─── Decision History ────────────────────────────────────────────────────────

export interface DecisionHistoryEntry {
  id: string;
  action: DecisionAction;
  actor: string;
  actor_role: string;
  rationale: string;
  timestamp: string;
  previous_status: ApprovalStatus;
  new_status: ApprovalStatus;
}

// ─── Approval Request ────────────────────────────────────────────────────────

export interface ApprovalRequest {
  id: string;
  risk_score: number;
  confidence_score: number;
  queue_type: QueueType;
  priority: Priority;
  status: ApprovalStatus;
  assigned_to: string | null;
  assigned_to_name: string | null;
  created_at: string;
  updated_at: string;
  booking_context: BookingContext;
  evidence: EvidenceItem[];
  risk_assessment: RiskAssessment;
  decision_history: DecisionHistoryEntry[];
  version: number; // optimistic locking
}

// ─── API Payloads ─────────────────────────────────────────────────────────────

export interface DecisionPayload {
  action: 'approve' | 'reject' | 'escalate' | 'withdraw';
  rationale: string;
  version: number;
  force?: boolean;
}

export interface AssignPayload {
  assignee_id: string;
  assignee_name: string;
}

// ─── Filter State ─────────────────────────────────────────────────────────────

export interface ApprovalFiltersState {
  search: string;
  queueType: QueueType | 'all';
  priority: Priority | 'all';
  assignedStatus: 'all' | 'assigned' | 'unassigned';
  status: ApprovalStatus | 'all';
}

// ─── Queue Stats ──────────────────────────────────────────────────────────────

export interface QueueStats {
  highRisk: number;
  lowConfidence: number;
  urgent: number;
  total: number;
  inReview: number;
}

// ─── Conflict State ───────────────────────────────────────────────────────────

export interface ConflictState {
  requestId: string;
  localVersion: number;
  serverVersion: number;
  serverStatus: ApprovalStatus;
  serverUpdatedBy: string;
  intendedAction: 'approve' | 'reject' | 'escalate' | 'withdraw';
  intendedRationale: string;
}

// ─── Audit Log ────────────────────────────────────────────────────────────────

export interface AuditLog {
  id: string;
  timestamp: string;
  actor: string;
  actor_role: string;
  action: string;
  entity_type: string;
  entity_id: string;
  payload_hash: string;
  previous_hash: string | null;
  verification_timestamp: string;
  integrity_status: IntegrityStatus;
  details: Record<string, unknown>;
}

// ─── System Config ────────────────────────────────────────────────────────────

export interface SystemConfig {
  high_risk_threshold: number;
  low_confidence_threshold: number;
  auto_escalation_timeout_minutes: number;
  notification_email_enabled: boolean;
  notification_slack_enabled: boolean;
  notification_webhook_url: string;
  updated_at: string;
  updated_by: string;
}

export interface ConfigUpdatePayload {
  high_risk_threshold?: number;
  low_confidence_threshold?: number;
  auto_escalation_timeout_minutes?: number;
  notification_email_enabled?: boolean;
  notification_slack_enabled?: boolean;
  notification_webhook_url?: string;
}
