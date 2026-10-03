// ─── ChatPage ─────────────────────────────────────────────────────────────────
// Route: /conversations/new
import React from 'react';
import MainLayout from '@/components/layout/MainLayout';
import PolicyEngine from '@/features/policies/components/PolicyEngine';

const ChatPage: React.FC = () => {
  return (
    <MainLayout>
      <div className="h-full flex flex-col">
        <PolicyEngine />
      </div>
    </MainLayout>
  );
};

export default ChatPage;
