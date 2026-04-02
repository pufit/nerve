import type { ChatMessage } from '../../types/chat';
import { BlockRenderer } from './BlockRenderer';

export function AssistantMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="py-4 px-5 bg-bg-sunken" data-role="assistant">
      <div className="max-w-3xl mx-auto">
        <div className="flex gap-3">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium shrink-0 mt-0.5 bg-[#6366f1]/20 text-[#6366f1]">
            N
          </div>
          <div className="min-w-0 flex-1">
            <BlockRenderer blocks={message.blocks} />
          </div>
        </div>
      </div>
    </div>
  );
}
