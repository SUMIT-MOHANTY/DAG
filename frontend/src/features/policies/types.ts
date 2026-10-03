// ─── Policy & Chat Domain Types ─────────────────────────────────────────────

export interface PlanStep {
  step: number;
  action: string;
  input: string;
  output: string;
  timestamp: string;
  tool?: string;
  duration_ms?: number;
  status?: 'pending' | 'running' | 'done' | 'error';
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent_plan?: PlanStep[];
  created_at: string;
  streaming?: boolean;
  approval_request_id?: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  status: 'active' | 'completed' | 'archived';
  messages: Message[];
  created_at: string;
  updated_at: string;
  context?: BookingContext;
}

export interface BookingContext {
  booking_id: string;
  property?: string;
  room_type?: string;
  adult_count: number;
  child_count: number;
  child_ages?: number[];
  check_in?: string;
  check_out?: string;
}

export interface PolicyEvaluationRequest {
  query: string;
  context?: BookingContext;
  conversation_id?: string;
}

export interface PolicyEvaluationResponse {
  conversation_id: string;
  message_id: string;
  content: string;
  agent_plan: PlanStep[];
  approval_required?: boolean;
  approval_request_id?: string;
}

export interface StreamChunk {
  type: 'token' | 'plan_step' | 'done' | 'error';
  content?: string;
  step?: PlanStep;
  error?: string;
}

export interface PolicyRule {
  id: string;
  name: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  applies_to: string[];
  conditions: Record<string, unknown>;
}
