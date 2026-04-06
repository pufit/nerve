import { useState, useRef, useEffect } from 'react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface Props {
  content: string;
  rawContent: string | null;
  summary: string;
}

export function EmailRenderer({ content, rawContent, summary }: Props) {
  const [showHtml, setShowHtml] = useState(!!rawContent);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeHeight, setIframeHeight] = useState(400);

  // Auto-resize iframe to content height
  useEffect(() => {
    if (!showHtml || !iframeRef.current) return;

    const resize = () => {
      const iframe = iframeRef.current;
      if (!iframe) return;
      try {
        const height = iframe.contentDocument?.documentElement?.scrollHeight;
        if (height && height > 100) {
          setIframeHeight(Math.min(height + 32, 2000));
        }
      } catch {
        // cross-origin safety — ignore
      }
    };

    // Resize after load and on subsequent renders
    const iframe = iframeRef.current;
    iframe.addEventListener('load', resize);
    return () => iframe.removeEventListener('load', resize);
  }, [showHtml]);

  if (!rawContent) {
    return <MarkdownRenderer content={content} />;
  }

  // Inject base styles for dark-mode-friendly rendering.
  // Many HTML emails have hardcoded light backgrounds — we let those render
  // as-is since the iframe isolates them.  The base styles provide sensible
  // defaults for emails without explicit styling.
  const styledHtml = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #222;
  background: #fff;
  padding: 16px;
  margin: 0;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
a { color: #4f46e5; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; max-width: 100%; }
td, th { padding: 4px 8px; }
pre { white-space: pre-wrap; }
</style></head>
<body>${rawContent}</body></html>`;

  return (
    <div>
      {/* Toggle between HTML and text views */}
      <div className="flex items-center gap-1 mb-3">
        <button
          onClick={() => setShowHtml(true)}
          className={`text-[12px] px-2 py-1 rounded transition-colors cursor-pointer
            ${showHtml ? 'bg-accent/15 text-accent' : 'text-text-dim hover:text-text-muted'}`}
        >
          HTML
        </button>
        <button
          onClick={() => setShowHtml(false)}
          className={`text-[12px] px-2 py-1 rounded transition-colors cursor-pointer
            ${!showHtml ? 'bg-accent/15 text-accent' : 'text-text-dim hover:text-text-muted'}`}
        >
          Text
        </button>
      </div>

      {showHtml ? (
        <iframe
          ref={iframeRef}
          srcDoc={styledHtml}
          sandbox="allow-same-origin"
          className="w-full border border-border-subtle rounded-lg bg-white"
          style={{ height: `${iframeHeight}px` }}
          title={summary}
        />
      ) : (
        <MarkdownRenderer content={content} />
      )}
    </div>
  );
}
