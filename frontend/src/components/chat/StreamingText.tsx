// ─── StreamingText ────────────────────────────────────────────────────────────
// Renders text with a blinking cursor while streaming
import React from 'react';

interface StreamingTextProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
}

const StreamingText: React.FC<StreamingTextProps> = ({
  content,
  isStreaming = false,
  className = '',
}) => {
  return (
    <span className={`whitespace-pre-wrap break-words ${className}`}>
      {content}
      {isStreaming && (
        <span
          className="inline-block w-0.5 h-4 bg-primary-500 ml-0.5 align-middle animate-[blink_1s_step-end_infinite]"
          aria-hidden="true"
        />
      )}
    </span>
  );
};

export default StreamingText;
