import { isDemo } from '../lib/demo';
import { Icon } from './ui/Icon';

const REPO_URL = 'https://github.com/Kunal0626/ResNav';

/**
 * Says, on every page, that this deployment has no backend.
 *
 * It is deliberately not dismissible. A visitor who misses it would read the
 * frozen numbers as live and the refused actions as bugs, and the point of
 * the demo is to show the project honestly, not to look finished.
 */
export function DemoBanner() {
  if (!isDemo) return null;

  return (
    <div className="demo-banner" role="note">
      <Icon name="info" className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <p>
        <strong>Read-only demo.</strong> Every figure here is a real snapshot of the
        seeded database, served as static files. Allocation, request creation and
        free-text search need the live API and a MySQL server, so they are disabled
        here &mdash;{' '}
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          run it locally
        </a>{' '}
        to use them.
      </p>
    </div>
  );
}
