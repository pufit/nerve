import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
  content: string;
  muted?: boolean;
}

export function MarkdownRenderer({ content, muted = false }: Props) {
  return (
    <div className={`prose prose-invert prose-sm max-w-none
      prose-headings:text-text prose-a:text-accent prose-code:text-text-secondary
      prose-pre:bg-surface prose-pre:border prose-pre:border-border-subtle
      ${muted ? 'text-text-muted' : 'text-text-secondary'}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content || '*(empty)*'}
      </ReactMarkdown>
    </div>
  );
}
