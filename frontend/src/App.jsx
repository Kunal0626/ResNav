import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ErrorBoundary } from './components/layout/ErrorBoundary';
import { SkeletonCard } from './components/ui';
import { Home } from './pages/Home';

// Home is bundled eagerly since it is the landing route; everything else is
// split so the initial download stays small.
const Results = lazy(() => import('./pages/Results').then((m) => ({ default: m.Results })));
const CommandCenter = lazy(() =>
  import('./pages/CommandCenter').then((m) => ({ default: m.CommandCenter })),
);
const Insights = lazy(() => import('./pages/Insights').then((m) => ({ default: m.Insights })));
const Forecast = lazy(() => import('./pages/Forecast').then((m) => ({ default: m.Forecast })));
const Risk = lazy(() => import('./pages/Risk').then((m) => ({ default: m.Risk })));
const Recommend = lazy(() => import('./pages/Recommend').then((m) => ({ default: m.Recommend })));
const Simulation = lazy(() => import('./pages/Simulation').then((m) => ({ default: m.Simulation })));
const NlpConsole = lazy(() => import('./pages/NlpConsole').then((m) => ({ default: m.NlpConsole })));
const Anomaly = lazy(() => import('./pages/Anomaly').then((m) => ({ default: m.Anomaly })));
const Explorer = lazy(() => import('./pages/Explorer').then((m) => ({ default: m.Explorer })));
const Requests = lazy(() => import('./pages/Requests').then((m) => ({ default: m.Requests })));
const Stock = lazy(() => import('./pages/Stock').then((m) => ({ default: m.Stock })));
const Allocations = lazy(() =>
  import('./pages/Allocations').then((m) => ({ default: m.Allocations })),
);
const Logs = lazy(() => import('./pages/Logs').then((m) => ({ default: m.Logs })));
const NotFound = lazy(() => import('./pages/NotFound').then((m) => ({ default: m.NotFound })));

function RouteFallback() {
  return (
    <div className="space-y-6">
      <SkeletonCard rows={2} />
      <SkeletonCard rows={5} />
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          path="/"
          element={
            <ErrorBoundary>
              <Home />
            </ErrorBoundary>
          }
        />
        {[
          ['results', Results],
          ['command-center', CommandCenter],
          ['insights', Insights],
          ['forecast', Forecast],
          ['risk', Risk],
          ['recommend', Recommend],
          ['simulation', Simulation],
          ['nlp', NlpConsole],
          ['anomaly', Anomaly],
          ['explorer', Explorer],
          ['requests', Requests],
          ['stock', Stock],
          ['allocations', Allocations],
          ['logs', Logs],
        ].map(([path, Component]) => (
          <Route
            key={path}
            path={path}
            element={
              // Keyed per route so a crash on one page does not persist to the next.
              <ErrorBoundary key={path}>
                <Suspense fallback={<RouteFallback />}>
                  <Component />
                </Suspense>
              </ErrorBoundary>
            }
          />
        ))}

        {/* Paths from the original Flask app, kept working as redirects. */}
        <Route path="/dashboard" element={<Navigate to="/command-center" replace />} />
        <Route path="/stock-forecast" element={<Navigate to="/forecast" replace />} />
        <Route path="/ai/:page" element={<LegacyAiRedirect />} />

        <Route
          path="*"
          element={
            <Suspense fallback={<RouteFallback />}>
              <NotFound />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}

function LegacyAiRedirect() {
  const map = {
    risk: '/risk',
    simulation: '/simulation',
    nlp: '/nlp',
    anomaly: '/anomaly',
    insights: '/insights',
    recommend: '/recommend',
    'data-explorer': '/explorer',
  };
  const page = window.location.pathname.split('/').pop();
  return <Navigate to={map[page] ?? '/'} replace />;
}
