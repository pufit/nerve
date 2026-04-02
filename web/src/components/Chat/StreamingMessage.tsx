import type { MessageBlock } from '../../types/chat';
import { BlockRenderer } from './BlockRenderer';

export function StreamingMessage({ blocks }: { blocks: MessageBlock[] }) {
  if (blocks.length === 0) {
    return (
      <div className="py-4 px-5 bg-bg-sunken">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-[#6366f1]/20 flex items-center justify-center text-xs font-medium text-[#6366f1] shrink-0">
              N
            </div>
            <div className="pt-1.5">
              <span className="streaming-cursor inline-block w-2 h-4 bg-[#6366f1]" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="py-4 px-5 bg-bg-sunken">
      <div className="max-w-3xl mx-auto">
        <div className="flex gap-3">
          <div className="w-7 h-7 rounded-full bg-[#6366f1]/20 flex items-center justify-center text-xs font-medium text-[#6366f1] shrink-0 mt-0.5">
            N
          </div>
          <div className="min-w-0 flex-1">
            <BlockRenderer blocks={blocks} streaming />
          </div>
        </div>
      </div>
    </div>
  );
}
