import { useMemo } from 'react';
import type { MessageBlock } from '../../types/chat';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolCallBlock } from './ToolCallBlock';
import { ToolCallGroupBlock } from './ToolCallGroupBlock';
import { MarkdownContent } from './MarkdownContent';
import { groupToolCalls } from '../../utils/groupToolCalls';

interface BlockRendererProps {
  blocks: MessageBlock[];
  /** Show streaming cursor on last block + streaming prop on last ThinkingBlock. */
  streaming?: boolean;
  /** Tailwind bg class for text cursor (default: 'bg-accent'). */
  cursorColor?: string;
  /** Optional wrapper class for text blocks (e.g. 'text-[13px] my-1'). */
  textClassName?: string;
}

export function BlockRenderer({
  blocks,
  streaming = false,
  cursorColor = 'bg-accent',
  textClassName,
}: BlockRendererProps) {
  const renderItems = useMemo(() => groupToolCalls(blocks), [blocks]);

  return (
    <>
      {renderItems.map((item, i) => {
        const isLast = streaming && i === renderItems.length - 1;

        switch (item.type) {
          case 'thinking':
            return <ThinkingBlock key={i} content={item.content} streaming={isLast} />;
          case 'tool_call':
            return <ToolCallBlock key={i} block={item} />;
          case 'tool_call_group':
            return <ToolCallGroupBlock key={i} group={item} />;
          case 'text': {
            const inner = (
              <>
                <MarkdownContent content={item.content} />
                {isLast && (
                  <span
                    className={`streaming-cursor inline-block w-1.5 h-4 ${cursorColor} ml-0.5 align-text-bottom`}
                  />
                )}
              </>
            );
            return textClassName ? (
              <div key={i} className={textClassName}>{inner}</div>
            ) : (
              <div key={i}>{inner}</div>
            );
          }
          default:
            return null;
        }
      })}
    </>
  );
}
