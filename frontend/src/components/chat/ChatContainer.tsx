// ─── ChatContainer ────────────────────────────────────────────────────────────
// Main chat layout: header + message list + input
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Message, BookingContext } from '@/features/policies/types';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import SuggestedQueries from './SuggestedQueries';
import ContextIndicator from './ContextIndicator';
import ContextDrawer from './ContextDrawer';

const DEFAULT_CONTEXT: BookingContext = {
  booking_id: 'BK-2847',
  adult_count: 2,
  child_count: 1,
  property: 'Grand Ocean Resort',
  room_type: 'family',
  child_ages: [8],
};

interface ChatContainerProps {
  messages: Message[];
  isStreaming: boolean;
  error: string | null;
  initialContext?: BookingContext;
  onSendMessage: (content: string, context?: BookingContext) => void;
  onCancelStream: () => void;
  onClearMessages: () => void;
  onApprovalTrigger?: (msg: Message) => void;
}

const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  isStreaming,
  error,
  initialContext,
  onSendMessage,
  onCancelStream,
  onClearMessages,
  onApprovalTrigger,
}) => {
  const [context, setContext] = useState<BookingContext>(
    initialContext ?? DEFAULT_CONTEXT
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);

  const handleSend = (content: string) => {
    onSendMessage(content, context);
    setPrefill(undefined);
  };

  const handleSuggestedQuery = (query: string) => {
    setPrefill(query);
  };

  const handleContextSave = (ctx: BookingContext) => {
    setContext(ctx);
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-full bg-neutral-50">
      {/* ── Header ── */}
      <div className="flex-shrink-0 bg-white border-b border-neutral-200 px-6 py-3">
        <div className="max-w-4xl mx-auto">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-1.5 text-2xs text-neutral-400 mb-2" aria-label="Breadcrumb">
            <Link to="/" className="hover:text-neutral-600 transition-colors">Home</Link>
            <span>/</span>
            <Link to="/conversations" className="hover:text-neutral-600 transition-colors">Conversations</Link>
            <span>/</span>
            <span className="text-neutral-600 font-medium">New Query</span>
          </nav>

          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-sm">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <div>
                <h1 className="text-base font-bold text-neutral-900">Ask About Restrictions</h1>
                <p className="text-2xs text-neutral-400">AI-powered policy evaluation with explainable reasoning</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <ContextIndicator context={context} onModify={() => setDrawerOpen(true)} />

              {messages.length > 0 && (
                <button
                  onClick={onClearMessages}
                  className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors px-2 py-1 rounded-lg hover:bg-neutral-100"
                  title="Clear conversation"
                >
                  Clear
                </button>
              )}

              <Link
                to="/conversations"
                className="text-xs font-medium text-primary-600 hover:text-primary-700 transition-colors"
              >
                View History →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="flex-shrink-0 bg-danger-50 border-b border-danger-200 px-6 py-2">
          <div className="max-w-4xl mx-auto flex items-center gap-2 text-danger-700">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs">{error}</span>
          </div>
        </div>
      )}

      {/* ── Main Content ── */}
      <div className="flex-1 overflow-hidden flex flex-col max-w-4xl w-full mx-auto">
        {isEmpty ? (
          <SuggestedQueries onSelect={handleSuggestedQuery} />
        ) : (
          <MessageList messages={messages} onApprovalClick={onApprovalTrigger} />
        )}
      </div>

      {/* ── Input ── */}
      <div className="flex-shrink-0">
        <ChatInput
          onSubmit={handleSend}
          isLoading={isStreaming}
          onCancel={onCancelStream}
          prefillValue={prefill}
        />
      </div>

      {/* ── Context Drawer ── */}
      <ContextDrawer
        isOpen={drawerOpen}
        context={context}
        onClose={() => setDrawerOpen(false)}
        onSave={handleContextSave}
      />
    </div>
  );
};

export default ChatContainer;
