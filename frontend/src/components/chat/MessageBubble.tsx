// ─── MessageBubble ────────────────────────────────────────────────────────────
import React from 'react';
import { Link } from 'react-router-dom';
import type { Message } from '@/features/policies/types';
import StreamingText from './StreamingText';
import ReasoningPanel from './ReasoningPanel';

interface MessageBubbleProps {
  message: Message;
  onApprovalClick?: (msg: Message) => void;
}

const UserAvatar: React.FC = () => (
  <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0 shadow-sm">
    <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z" />
    </svg>
  </div>
);

const AssistantAvatar: React.FC<{ streaming?: boolean }> = ({ streaming }) => (
  <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm ${streaming ? 'bg-primary-500 animate-pulse' : 'bg-gradient-to-br from-primary-500 to-primary-700'}`}>
    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  </div>
);

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onApprovalClick }) => {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  if (isUser) {
    return (
      <div className="flex items-end gap-2.5 justify-end animate-fade-in">
        <div className="max-w-[75%]">
          <div className="bg-primary-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 shadow-sm">
            <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{message.content}</p>
          </div>
          <p className="text-2xs text-neutral-400 text-right mt-1 pr-1">{formatTime(message.created_at)}</p>
        </div>
        <UserAvatar />
      </div>
    );
  }

  if (isAssistant) {
    const hasContent = message.content.length > 0;
    const hasApproval = !!message.approval_request_id;

    return (
      <div className="flex items-start gap-2.5 animate-fade-in">
        <AssistantAvatar streaming={message.streaming} />
        <div className="max-w-[80%] flex-1">
          <div className="bg-white border border-neutral-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-card">
            {message.streaming && !hasContent ? (
              <div className="flex items-center gap-2 text-neutral-400">
                <span className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce [animation-delay:300ms]" />
                </span>
                <span className="text-sm text-neutral-400 italic">Thinking...</span>
              </div>
            ) : (
              <StreamingText
                content={message.content}
                isStreaming={message.streaming}
                className="text-sm text-neutral-800 leading-relaxed"
              />
            )}

            {hasApproval && (
              <div className="mt-3 pt-3 border-t border-warning-200">
                <div className="flex items-center gap-2 text-warning-700 bg-warning-50 rounded-lg px-3 py-2">
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span className="text-xs font-medium">Human approval required</span>
                  <Link
                    to={`/approvals/${message.approval_request_id}`}
                    onClick={() => onApprovalClick?.(message)}
                    className="ml-auto text-xs font-semibold text-warning-700 underline hover:text-warning-800"
                  >
                    Review →
                  </Link>
                </div>
              </div>
            )}
          </div>

          <p className="text-2xs text-neutral-400 mt-1 pl-1">{formatTime(message.created_at)}</p>

          {/* Reasoning panel */}
          {isAssistant && message.agent_plan && message.agent_plan.length > 0 && (
            <ReasoningPanel steps={message.agent_plan} />
          )}
        </div>
      </div>
    );
  }

  return null;
};

export default MessageBubble;
