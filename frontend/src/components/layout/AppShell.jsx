import { useCallback, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useApi } from '../../hooks/useApi';
import { useIsDesktop } from '../../hooks/useMediaQuery';
import { api } from '../../lib/api';
import { Icon } from '../ui/Icon';
import { DemoBanner } from '../DemoBanner';
import { useTheme } from '../../contexts/ThemeContext';
import { Sidebar } from './Sidebar';
import { ToastViewport } from './ToastViewport';

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false);
  const isDesktop = useIsDesktop();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const fetchOverview = useCallback(({ signal }) => api.overview({ signal }), []);
  const { data: overview } = useApi(fetchOverview);
  const status = overview?.status;

  const closeNav = useCallback(() => setNavOpen(false), []);

  // Close the drawer when the route changes or the viewport grows to desktop.
  useEffect(() => {
    closeNav();
  }, [location.pathname, closeNav]);

  useEffect(() => {
    if (isDesktop) closeNav();
  }, [isDesktop, closeNav]);

  // Lock body scroll behind the mobile drawer.
  useEffect(() => {
    const locked = navOpen && !isDesktop;
    document.body.style.overflow = locked ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [navOpen, isDesktop]);

  // Move focus to the main region on navigation so screen readers announce the
  // new page instead of staying on a link in the sidebar.
  useEffect(() => {
    document.getElementById('main-content')?.focus({ preventScroll: true });
  }, [location.pathname]);

  return (
    <div className="mesh-bg min-h-screen text-[var(--rn-text)] antialiased">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <div className="layout-wrapper">
        {navOpen && !isDesktop ? (
          <div
            className="fixed inset-0 z-[35] bg-black/25 backdrop-blur-sm lg:hidden"
            onClick={closeNav}
            aria-hidden="true"
          />
        ) : null}

        <Sidebar open={navOpen || isDesktop} onClose={closeNav} status={status} />

        <div className="main-scroll-area">
          <DemoBanner />
          <header className="glass-header flex shrink-0 items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              className="g-icon-btn lg:hidden"
              aria-label="Open navigation"
              aria-expanded={navOpen}
              aria-controls="sidebar"
            >
              <Icon name="menu" className="h-[18px] w-[18px]" />
            </button>

            <Breadcrumb />

            <div className="flex items-center gap-2.5">
              <SystemPill status={status} />
              <button
                type="button"
                onClick={toggleTheme}
                className="g-icon-btn"
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                <Icon name={theme === 'dark' ? 'sun' : 'moon'} className="h-[18px] w-[18px]" />
              </button>
            </div>
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className="w-full flex-1 pb-12 focus:outline-none"
          >
            <div className="page-fade-in mx-auto w-full max-w-[1340px] px-4 pt-6 sm:px-6 lg:pr-8 lg:pl-2">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      <ToastViewport />
    </div>
  );
}

/** Where you are, in the header, so the floating sidebar is not the only
 *  thing telling you. Derived from the route rather than threaded through
 *  props, which keeps every page free of layout concerns. */
function Breadcrumb() {
  const { pathname } = useLocation();
  const name = pathname === '/' ? 'Overview' : LABELS[pathname.slice(1)] ?? 'ResNav';
  return (
    <p className="hidden flex-1 truncate pl-1 text-[0.8125rem] font-medium text-[var(--rn-text-2)] lg:block">
      {name}
    </p>
  );
}

const LABELS = {
  results: 'Search Results',
  'command-center': 'AI Command Center',
  insights: 'AI Insights',
  forecast: 'Depletion Forecast',
  risk: 'Zone Risk Prediction',
  recommend: 'Recommendation Engine',
  simulation: 'Simulation Lab',
  nlp: 'NLP Console',
  anomaly: 'Anomaly Detection',
  explorer: 'Data Explorer',
  requests: 'Resource Requests',
  stock: 'Live Stock',
  allocations: 'Allocation History',
  logs: 'System Logs',
};

function SystemPill({ status }) {
  const level = status?.level ?? 'nominal';
  const copy = {
    nominal: 'AI Systems Active',
    busy: 'Dispatch In Progress',
    degraded: 'Attention Required',
  };
  const dot = {
    nominal: 'bg-emerald-500',
    busy: 'bg-indigo-500',
    degraded: 'bg-amber-500',
  };

  return (
    <div className="status-pill hidden sm:inline-flex">
      <span className={`h-1.5 w-1.5 rounded-full ${dot[level]} pulse`} aria-hidden="true" />
      {copy[level]}
    </div>
  );
}
