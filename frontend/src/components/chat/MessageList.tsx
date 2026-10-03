// ─── MessageList ──────────────────────────────────────────────────────────────
import React, { useEffect, useRef } from 'react';
import type { Message } from '@/features/policies/types';
import MessageBubble from './MessageBubble';

interface MessageListProps {
  messages: Message[];
  onApprovalClick?: (msg: Message) => void;
}

const MessageList: React.FC<MessageListProps> = ({ messages, onApprovalClick }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or streaming updates
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 scroll-smooth">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          onApprovalClick={onApprovalClick}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
};

export default MessageList;
