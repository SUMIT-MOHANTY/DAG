// ─── ChatInput ────────────────────────────────────────────────────────────────
import React, { useState, useRef, useEffect } from 'react';

interface ChatInputProps {
  onSubmit: (message: string) => void;
  isLoading?: boolean;
  onCancel?: () => void;
  placeholder?: string;
  prefillValue?: string;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSubmit,
  isLoading = false,
  onCancel,
  placeholder = 'Ask about booking restrictions...',
  prefillValue,
}) => {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [value]);

  // Prefill from suggested queries
  useEffect(() => {
    if (prefillValue !== undefined) {
      setValue(prefillValue);
      textareaRef.current?.focus();
    }
  }, [prefillValue]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSubmit = value.trim().length > 0 && !isLoading;

  return (
    <div className="border-t border-neutral-200 bg-white px-4 py-3">
      <div className="max-w-4xl mx-auto">
        <div className={`flex items-end gap-2 rounded-2xl border transition-all duration-150 ${
          isLoading
            ? 'border-primary-300 bg-primary-50/30'
            : 'border-neutral-300 bg-white focus-within:border-primary-400 focus-within:shadow-soft'
        } px-3 py-2`}>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isLoading ? 'Waiting for response...' : placeholder}
            disabled={isLoading}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-neutral-800 placeholder-neutral-400 focus:outline-none leading-relaxed min-h-[24px] max-h-40 disabled:opacity-60"
            aria-label="Message input"
          />

          <div className="flex items-center gap-1.5 flex-shrink-0 pb-0.5">
            {isLoading && onCancel && (
              <button
                onClick={onCancel}
                className="px-2.5 py-1.5 text-xs font-medium text-neutral-500 hover:text-danger-600 hover:bg-danger-50 rounded-lg transition-colors"
                title="Cancel streaming"
              >
                Stop
              </button>
            )}
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150 ${
                canSubmit
                  ? 'bg-primary-600 hover:bg-primary-700 text-white shadow-sm hover:shadow'
                  : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
              }`}
              aria-label="Send message"
            >
              {isLoading ? (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </div>
        </div>

        <p className="text-2xs text-neutral-400 text-center mt-1.5">
          Press <kbd className="px-1 py-0.5 bg-neutral-100 rounded text-neutral-500 font-mono">Enter</kbd> to send ·{' '}
          <kbd className="px-1 py-0.5 bg-neutral-100 rounded text-neutral-500 font-mono">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
};

export default ChatInput;
