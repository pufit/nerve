import { useState } from 'react';
import { ChevronRight, ChevronDown, Brain } from 'lucide-react';

export function ThinkingBlock({ content, streaming }: { content: string; streaming?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const preview = content.split('\n')[0].slice(0, 100);

  return (
    <div className="my-2 border-l-2 border-border-subtle bg-bg-sunken rounded-r-md">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left cursor-pointer hover:bg-surface-hover rounded-r-md transition-colors"
      >
        <Brain size={14} className="text-accent shrink-0" />
        {expanded ? <ChevronDown size={14} className="text-text-faint" /> : <ChevronRight size={14} className="text-text-faint" />}
        <span className="text-[13px] text-text-muted italic truncate">
          {expanded ? 'Thinking' : preview || 'Thinking...'}
        </span>
        {streaming && <span className="streaming-cursor inline-block w-1.5 h-3.5 bg-accent ml-1 shrink-0" />}
      </button>
      {expanded && (
        <div className="px-4 pb-3 text-[13px] text-text-muted italic whitespace-pre-wrap leading-relaxed">
          {content}
          {streaming && <span className="streaming-cursor inline-block w-1.5 h-3.5 bg-accent ml-0.5 align-text-bottom" />}
        </div>
      )}
    </div>
  );
}
