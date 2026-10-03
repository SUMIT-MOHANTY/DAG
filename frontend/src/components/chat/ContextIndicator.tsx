// ─── ContextIndicator ────────────────────────────────────────────────────────
import React from 'react';
import type { BookingContext } from '@/features/policies/types';

interface ContextIndicatorProps {
  context: BookingContext;
  onModify: () => void;
}

const ContextIndicator: React.FC<ContextIndicatorProps> = ({ context, onModify }) => {
  const guestSummary = [
    context.adult_count > 0 && `${context.adult_count} Adult${context.adult_count !== 1 ? 's' : ''}`,
    context.child_count > 0 && `${context.child_count} Child${context.child_count !== 1 ? 'ren' : ''}`,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-primary-50 border border-primary-200 rounded-lg">
      <svg className="w-3.5 h-3.5 text-primary-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
      <span className="text-xs text-primary-700 font-medium">
        Context:{' '}
        <span className="font-semibold">{context.booking_id}</span>
        {guestSummary && <span className="text-primary-600">, {guestSummary}</span>}
        {context.property && <span className="text-primary-500"> · {context.property}</span>}
      </span>
      <button
        onClick={onModify}
        className="ml-1 text-2xs font-semibold text-primary-600 hover:text-primary-800 underline underline-offset-2 transition-colors"
      >
        Modify
      </button>
    </div>
  );
};

export default ContextIndicator;
