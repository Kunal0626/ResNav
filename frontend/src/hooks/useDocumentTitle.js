import { useEffect } from 'react';

const SUFFIX = 'ResNav AI';

/** Keeps the tab title in sync with the current page. */
export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} — ${SUFFIX}` : SUFFIX;
  }, [title]);
}
