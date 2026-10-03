// ─── usePolicies Hook ────────────────────────────────────────────────────────
import { useState, useCallback, useRef } from 'react';
import { streamPolicyEvaluation } from '../api';
import type {
  Message,
  BookingContext,
  PlanStep,
  StreamChunk,
} from '../types';

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function nowISO(): string {
  return new Date().toISOString();
}

export function usePolicies() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(
    (content: string, context?: BookingContext, conversationId?: string) => {
      if (isStreaming) return;

      setError(null);

      // 1. Append user message immediately
      const userMsg: Message = {
        id: generateId(),
        role: 'user',
        content,
        created_at: nowISO(),
      };

      // 2. Prepare streaming assistant placeholder
      const assistantId = generateId();
      const assistantMsg: Message = {
        id: assistantId,
        role: 'assistant',
        content: '',
        agent_plan: [],
        created_at: nowISO(),
        streaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      let accumulatedContent = '';
      const accumulatedPlan: PlanStep[] = [];

      const cancel = streamPolicyEvaluation(
        { query: content, context, conversation_id: conversationId },
        (chunk: StreamChunk) => {
          if (chunk.type === 'token' && chunk.content) {
            accumulatedContent += chunk.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: accumulatedContent }
                  : m
              )
            );
          } else if (chunk.type === 'plan_step' && chunk.step) {
            accumulatedPlan.push(chunk.step);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, agent_plan: [...accumulatedPlan] }
                  : m
              )
            );
          }
        },
        () => {
          // Done
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, streaming: false } : m
            )
          );
          setIsStreaming(false);
          cancelRef.current = null;
        },
        (err) => {
          setError(err.message);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content:
                      accumulatedContent ||
                      'An error occurred while processing your request.',
                    streaming: false,
                  }
                : m
            )
          );
          setIsStreaming(false);
          cancelRef.current = null;
        }
      );

      cancelRef.current = cancel;
    },
    [isStreaming]
  );

  const cancelStream = useCallback(() => {
    cancelRef.current?.();
    cancelRef.current = null;
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m))
    );
  }, []);

  const clearMessages = useCallback(() => {
    cancelStream();
    setMessages([]);
    setError(null);
  }, [cancelStream]);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    cancelStream,
    clearMessages,
    setMessages,
  };
}
