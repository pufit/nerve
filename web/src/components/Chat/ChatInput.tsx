import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { Send, Square, X, Plus, Trash2, Sparkles, HelpCircle, StickyNote } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import type { QuoteAction, QuoteEntry } from '../../stores/chatStore';

const ACTION_CONFIG: Record<QuoteAction, { icon: typeof Plus; label: string; color: string; placeholder: string }> = {
  add:      { icon: Plus,       label: 'Add',     color: '#6366f1', placeholder: 'Instructions...' },
  remove:   { icon: Trash2,     label: 'Remove',  color: '#ef4444', placeholder: 'Instructions...' },
  improve:  { icon: Sparkles,   label: 'Improve', color: '#a855f7', placeholder: 'Instructions...' },
  question: { icon: HelpCircle, label: 'Ask',     color: '#f59e0b', placeholder: 'What do you want to know?' },
  note:     { icon: StickyNote, label: 'Note',    color: '#6b7280', placeholder: 'Your note...' },
};

// Actions that auto-focus the instruction input (need user input)
const FOCUS_ACTIONS = new Set<QuoteAction>(['add', 'question', 'note']);

export function ChatInput({ onSend, onStop, isStreaming, disabled }: {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lastInstructionRef = useRef<HTMLInputElement>(null);

  const quotes = useChatStore(s => s.quotes);
  const removeQuote = useChatStore(s => s.removeQuote);
  const updateQuoteInstruction = useChatStore(s => s.updateQuoteInstruction);
  const clearQuotes = useChatStore(s => s.clearQuotes);

  const [prevQuoteCount, setPrevQuoteCount] = useState(0);

  // Auto-focus instruction input when a new quote is added
  useEffect(() => {
    if (quotes.length > prevQuoteCount && quotes.length > 0) {
      const last = quotes[quotes.length - 1];
      if (FOCUS_ACTIONS.has(last.action)) {
        // Focus the instruction input of the last quote
        setTimeout(() => lastInstructionRef.current?.focus(), 0);
      }
    }
    setPrevQuoteCount(quotes.length);
  }, [quotes.length, prevQuoteCount, quotes]);

  const composeMessage = (): string => {
    const parts: string[] = [];
    const ACTION_LABELS: Record<QuoteAction, string> = {
      add: 'Add', remove: 'Remove', improve: 'Improve', question: 'Question', note: 'Note',
    };

    for (const q of quotes) {
      const blockquote = q.text.split('\n').map(l => `> ${l}`).join('\n');
      const instr = q.instruction.trim();
      const label = ACTION_LABELS[q.action];
      parts.push(instr ? `${blockquote}\n${label}: ${instr}` : blockquote);
    }

    if (input.trim()) {
      parts.push(input.trim());
    }

    return parts.join('\n\n');
  };

  const canSend = !disabled && !isStreaming && (input.trim() || quotes.length > 0);

  const handleSend = () => {
    const message = composeMessage();
    if (!message) return;
    onSend(message);
    setInput('');
    clearQuotes();
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (canSend) handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  };

  return (
    <div className="border-t border-border-subtle bg-bg shrink-0">
      {/* Quote cards */}
      {quotes.length > 0 && (
        <div className="px-4 pt-3 pb-1">
          <div className="max-w-3xl mx-auto space-y-2">
            {quotes.map((quote, idx) => (
              <QuoteCard
                key={quote.id}
                quote={quote}
                instructionRef={idx === quotes.length - 1 ? lastInstructionRef : undefined}
                onRemove={() => removeQuote(quote.id)}
                onUpdateInstruction={(v) => updateQuoteInstruction(quote.id, v)}
                onSend={canSend ? handleSend : undefined}
              />
            ))}
          </div>
        </div>
      )}

      {/* Main input */}
      <div className="px-4 py-3">
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); handleInput(); }}
            onKeyDown={handleKeyDown}
            placeholder={quotes.length > 0 ? 'Add context (optional)...' : 'Send a message...'}
            rows={1}
            disabled={disabled}
            className="flex-1 px-4 py-3 bg-surface-raised border border-border rounded-xl text-[15px] text-text outline-none focus:border-[#6366f1]/50 resize-none disabled:opacity-50 placeholder:text-text-faint"
          />
          {isStreaming ? (
            <button
              onClick={onStop}
              className="w-10 h-10 bg-red-500/80 hover:bg-red-500 text-white rounded-xl flex items-center justify-center cursor-pointer transition-colors shrink-0"
              title="Stop generation"
            >
              <Square size={16} />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!canSend}
              className="w-10 h-10 bg-[#6366f1] hover:bg-[#818cf8] text-white rounded-xl flex items-center justify-center disabled:opacity-30 cursor-pointer transition-colors shrink-0"
            >
              <Send size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


function QuoteCard({ quote, instructionRef, onRemove, onUpdateInstruction, onSend }: {
  quote: QuoteEntry;
  instructionRef?: React.RefObject<HTMLInputElement | null>;
  onRemove: () => void;
  onUpdateInstruction: (v: string) => void;
  onSend?: () => void;
}) {
  const config = ACTION_CONFIG[quote.action];
  const Icon = config.icon;
  const truncated = quote.text.length > 120 ? quote.text.slice(0, 120) + '…' : quote.text;

  return (
    <div
      className="quote-card rounded-lg bg-surface border border-border overflow-hidden"
      style={{ borderLeftColor: config.color, borderLeftWidth: '3px' }}
    >
      <div className="flex items-start gap-2 px-3 py-2">
        {/* Icon + label */}
        <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
          <Icon size={13} style={{ color: config.color }} />
          <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: config.color }}>
            {config.label}
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="text-[12px] text-text-muted leading-relaxed line-clamp-2">{truncated}</div>
          <input
            ref={instructionRef}
            type="text"
            value={quote.instruction}
            onChange={(e) => onUpdateInstruction(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && onSend) { e.preventDefault(); onSend(); } }}
            placeholder={config.placeholder}
            className="w-full mt-1.5 px-0 py-0.5 bg-transparent text-[13px] text-text-secondary outline-none placeholder:text-text-faint border-b border-border focus:border-border transition-colors"
          />
        </div>

        {/* Remove */}
        <button
          onClick={onRemove}
          className="text-text-faint hover:text-text-muted cursor-pointer transition-colors shrink-0 pt-0.5"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
