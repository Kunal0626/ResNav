import { usePrefersReducedMotion } from '../hooks/useMediaQuery';

/**
 * Scrolling status strip. Pauses on hover and focus, and falls back to a static
 * list when the user prefers reduced motion.
 */
export function Ticker({ messages = [] }) {
  const reducedMotion = usePrefersReducedMotion();
  if (!messages.length) return null;

  if (reducedMotion) {
    return (
      <div className="dash-card overflow-hidden px-5 py-3">
        <ul className="space-y-1.5 text-xs text-[var(--rn-text-2)]">
          {messages.map((message) => (
            <li key={message} className="flex gap-2">
              <span className="text-indigo-500" aria-hidden="true">
                ·
              </span>
              {message}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="dash-card ticker py-2.5" role="marquee" aria-label="Live system status">
      {/* Duplicated so the -50% translate loops seamlessly. */}
      <div className="ticker-track">
        {[...messages, ...messages].map((message, index) => (
          <span
            key={`${message}-${index}`}
            className="whitespace-nowrap text-xs text-[var(--rn-text-2)]"
            aria-hidden={index >= messages.length}
          >
            <span className="mr-2 text-indigo-500" aria-hidden="true">
              ●
            </span>
            {message}
          </span>
        ))}
      </div>
    </div>
  );
}
