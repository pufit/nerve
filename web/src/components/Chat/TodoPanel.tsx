import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import type { TodoItem } from '../../stores/chatStore';

export function TodoPanel({ todos }: { todos: TodoItem[] }) {
  const [visible, setVisible] = useState(true);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevTodosRef = useRef<TodoItem[]>([]);

  const allDone = todos.length > 0 && todos.every(t => t.status === 'completed');

  // Auto-hide 5s after all items complete
  useEffect(() => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }

    if (allDone) {
      hideTimer.current = setTimeout(() => setVisible(false), 5000);
    } else {
      setVisible(true);
    }

    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, [allDone]);

  // Reset visibility when todos change from empty
  useEffect(() => {
    if (prevTodosRef.current.length === 0 && todos.length > 0) {
      setVisible(true);
    }
    prevTodosRef.current = todos;
  }, [todos]);

  if (todos.length === 0 || !visible) return null;

  return (
    <div className={`border-t border-border-subtle bg-bg-sunken shrink-0 transition-all duration-300 ${allDone ? 'opacity-60' : ''}`}>
      <div className="max-w-3xl mx-auto px-5 py-2.5">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[11px] font-medium text-text-faint uppercase tracking-wider">Tasks</span>
          <span className="text-[10px] text-text-faint">
            {todos.filter(t => t.status === 'completed').length}/{todos.length}
          </span>
        </div>
        <div className="space-y-0.5">
          {todos.map((todo, i) => (
            <TodoRow key={`${i}-${todo.content}`} todo={todo} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TodoRow({ todo }: { todo: TodoItem }) {
  const isCompleted = todo.status === 'completed';
  const isActive = todo.status === 'in_progress';

  return (
    <div className={`todo-row flex items-center gap-2 py-0.5 text-[13px] transition-opacity duration-300 ${isCompleted ? 'opacity-50' : ''}`}>
      {isCompleted ? (
        <CheckCircle2 size={14} className="text-hue-green shrink-0 todo-icon-enter" />
      ) : isActive ? (
        <Loader2 size={14} className="text-accent shrink-0 animate-spin" />
      ) : (
        <Circle size={14} className="text-text-faint shrink-0" />
      )}
      <span className={`${isCompleted ? 'line-through text-text-faint' : isActive ? 'text-text' : 'text-text-muted'} transition-colors duration-300`}>
        {isActive ? todo.activeForm : todo.content}
      </span>
    </div>
  );
}
