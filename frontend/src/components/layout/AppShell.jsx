import { useCallback, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useApi } from '../../hooks/useApi';
import { useIsDesktop } from '../../hooks/useMediaQuery';
import { api } from '../../lib/api';
import { Icon } from '../ui/Icon';
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
    <div className="mesh-bg min-h-screen text-sand-600 antialiased dark:text-neutral-200">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <div className="layout-wrapper">
        {navOpen && !isDesktop ? (
          <div
            className="fixed inset-0 z-30 bg-black/40 lg:hidden"
            onClick={closeNav}
            aria-hidden="true"
          />
        ) : null}

        <Sidebar open={navOpen || isDesktop} onClose={closeNav} status={status} />

        <div className="main-scroll-area">
          <header className="glass-header sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-3 px-4 sm:px-6 lg:justify-end">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              className="-ml-2 rounded-lg p-2 text-sand-400 hover:text-sand-600 dark:text-neutral-500 dark:hover:text-neutral-200 lg:hidden"
              aria-label="Open navigation"
              aria-expanded={navOpen}
              aria-controls="sidebar"
            >
              <Icon name="menu" className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3">
              <SystemPill status={status} />

              <button
                type="button"
                onClick={toggleTheme}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-sand-200 text-sand-400 transition-colors hover:bg-sand-200/50 dark:border-neutral-750 dark:text-neutral-500 dark:hover:bg-neutral-750/50"
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                <Icon name={theme === 'dark' ? 'sun' : 'moon'} className="h-4 w-4" />
              </button>
            </div>
          </header>

          <main
            id="main-content"
            tabIndex={-1}
            className="w-full flex-1 pb-12 focus:outline-none"
          >
            <div className="page-fade-in mx-auto w-full max-w-[1440px] p-4 sm:p-6 lg:p-8">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      <ToastViewport />
    </div>
  );
}

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
