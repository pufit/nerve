import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, HelpCircle, X } from 'lucide-react';
import { useNotificationStore } from '../../stores/notificationStore';

const TOAST_DURATION = 5000;

export function NotificationToast() {
  const { toastQueue, dismissToast, answerNotification } = useNotificationStore();
  const navigate = useNavigate();

  // Auto-dismiss toasts after duration
  useEffect(() => {
    if (toastQueue.length === 0) return;
    const timer = setTimeout(() => {
      dismissToast(toastQueue[0].id);
    }, TOAST_DURATION);
    return () => clearTimeout(timer);
  }, [toastQueue]);

  if (toastQueue.length === 0) return null;

  // Show max 3 toasts
  const visible = toastQueue.slice(0, 3);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {visible.map((notif) => {
        const isQuestion = notif.type === 'question';
        const options = notif.options ? (typeof notif.options === 'string' ? JSON.parse(notif.options) : notif.options) : null;

        return (
          <div
            key={notif.id}
            className="bg-surface-raised border border-border-subtle rounded-lg shadow-xl p-3 animate-slide-in"
          >
            <div className="flex items-start gap-2">
              {isQuestion ? (
                <HelpCircle size={16} className="text-blue-400 shrink-0 mt-0.5" />
              ) : (
                <Bell size={16} className="text-[#6366f1] shrink-0 mt-0.5" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p
                    className="text-sm font-medium text-text cursor-pointer hover:text-[#6366f1]"
                    onClick={() => {
                      navigate('/notifications');
                      dismissToast(notif.id);
                    }}
                  >
                    {notif.title}
                  </p>
                  <button
                    onClick={() => dismissToast(notif.id)}
                    className="text-text-faint hover:text-text-muted shrink-0 cursor-pointer"
                  >
                    <X size={14} />
                  </button>
                </div>
                {notif.body && (
                  <p className="text-xs text-text-muted mt-0.5 line-clamp-2">{notif.body}</p>
                )}
                {/* Quick answer buttons for questions */}
                {isQuestion && options && notif.status === 'pending' && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {options.slice(0, 3).map((opt: string) => (
                      <button
                        key={opt}
                        onClick={() => {
                          answerNotification(notif.id, opt);
                          dismissToast(notif.id);
                        }}
                        className="px-2 py-0.5 bg-[#6366f1]/15 text-[#6366f1] rounded text-xs border border-[#6366f1]/30 hover:bg-[#6366f1]/25 cursor-pointer"
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
