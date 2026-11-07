import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Renders children at the end of <body>.
 *
 * Necessary for overlays: the page container carries a `transform` from its
 * entrance animation, and any transformed ancestor becomes the containing block
 * for `position: fixed` descendants. Without a portal a full-screen modal is
 * clipped to the page container instead of the viewport.
 */
export function Portal({ children }) {
  const [container] = useState(() =>
    typeof document === 'undefined' ? null : document.createElement('div'),
  );

  useEffect(() => {
    if (!container) return undefined;
    container.setAttribute('data-portal', '');
    document.body.appendChild(container);
    return () => {
      document.body.removeChild(container);
    };
  }, [container]);

  return container ? createPortal(children, container) : null;
}
