import { useToast } from '../../contexts/ToastContext';
import { Icon } from '../ui/Icon';

const TONES = {
  success: { icon: 'check', ring: 'border-emerald-500/40', accent: 'text-emerald-500' },
  error: { icon: 'alert', ring: 'border-red-500/40', accent: 'text-red-500' },
  info: { icon: 'info', ring: 'border-indigo-500/40', accent: 'text-indigo-500' },
};

export function ToastViewport() {
  const { toasts, dismiss } = useToast();
  if (!toasts.length) return null;

  return (
    <div
      className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:items-end"
      role="region"
      aria-label="Notifications"
    >
      {toasts.map((toast) => {
        const tone = TONES[toast.tone] ?? TONES.info;
        return (
          <div
            key={toast.id}
            role="status"
            aria-live="polite"
            className={`float-up pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border ${tone.ring} bg-[var(--rn-surface)] p-3.5 shadow-lg`}
          >
            <Icon name={tone.icon} className={`mt-0.5 h-4 w-4 shrink-0 ${tone.accent}`} />
            <p className="flex-1 text-xs leading-relaxed text-[var(--rn-text)]">{toast.message}</p>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="shrink-0 rounded p-0.5 text-[var(--rn-text-3)] transition-colors hover:text-[var(--rn-text)]"
              aria-label="Dismiss notification"
            >
              <Icon name="close" className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
