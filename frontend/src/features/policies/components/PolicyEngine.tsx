// ─── PolicyEngine ────────────────────────────────────────────────────────────
// Orchestrates policy evaluation and surfaces approval triggers
import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { Message, BookingContext } from '../types';
import { usePolicies } from '../hooks/usePolicies';
import ChatContainer from '@/components/chat/ChatContainer';

interface PolicyEngineProps {
  initialContext?: BookingContext;
}

const PolicyEngine: React.FC<PolicyEngineProps> = ({ initialContext }) => {
  const navigate = useNavigate();
  const { messages, isStreaming, error, sendMessage, cancelStream, clearMessages } =
    usePolicies();

  const handleApprovalTrigger = (msg: Message) => {
    if (msg.approval_request_id) {
      navigate(`/approvals/${msg.approval_request_id}`);
    }
  };

  return (
    <ChatContainer
      messages={messages}
      isStreaming={isStreaming}
      error={error}
      initialContext={initialContext}
      onSendMessage={sendMessage}
      onCancelStream={cancelStream}
      onClearMessages={clearMessages}
      onApprovalTrigger={handleApprovalTrigger}
    />
  );
};

export default PolicyEngine;
