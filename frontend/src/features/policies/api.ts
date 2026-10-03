// ─── Policies API Client ─────────────────────────────────────────────────────
import apiClient from '@/utils/apiClient';
import type {
  PolicyEvaluationRequest,
  PolicyEvaluationResponse,
  Conversation,
  StreamChunk,
} from './types';

const BASE = '/api/v1';

// ── Conversations ─────────────────────────────────────────────────────────────

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await apiClient.get<Conversation[]>(`${BASE}/conversations`);
  return res.data;
}

export async function fetchConversation(id: string): Promise<Conversation> {
  const res = await apiClient.get<Conversation>(`${BASE}/conversations/${id}`);
  return res.data;
}

export async function createConversation(): Promise<Conversation> {
  const res = await apiClient.post<Conversation>(`${BASE}/conversations`, {});
  return res.data;
}

// ── Policy Evaluation (non-streaming) ────────────────────────────────────────

export async function evaluatePolicy(
  payload: PolicyEvaluationRequest
): Promise<PolicyEvaluationResponse> {
  const res = await apiClient.post<PolicyEvaluationResponse>(
    `${BASE}/policies/evaluate`,
    payload
  );
  return res.data;
}

// ── SSE Streaming ─────────────────────────────────────────────────────────────

export function streamPolicyEvaluation(
  payload: PolicyEvaluationRequest,
  onChunk: (chunk: StreamChunk) => void,
  onDone: () => void,
  onError: (err: Error) => void
): () => void {
  const url = new URL(`${window.location.origin}${BASE}/policies/stream`);

  let aborted = false;
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (!aborted) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const raw = line.slice(6).trim();
            if (raw === '[DONE]') {
              onDone();
              return;
            }
            try {
              const chunk: StreamChunk = JSON.parse(raw);
              onChunk(chunk);
            } catch {
              // ignore malformed chunks
            }
          }
        }
      }
      onDone();
    } catch (err) {
      if (!aborted) onError(err instanceof Error ? err : new Error(String(err)));
    }
  })();

  return () => {
    aborted = true;
    controller.abort();
  };
}
