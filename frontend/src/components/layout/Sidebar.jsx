import { useEffect, useRef } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Icon } from '../ui/Icon';

/** Same grouping and order the original sidebar used, plus the Operations
 *  section whose pages previously had templates but no routes. */
const SECTIONS = [
  {
    title: 'Overview',
    items: [{ to: '/', label: 'Home', icon: 'home', end: true }],
  },
  {
    title: 'AI Intelligence',
    items: [
      { to: '/command-center', label: 'AI Command Center', icon: 'grid' },
      { to: '/insights', label: 'AI Insights', icon: 'bulb' },
      { to: '/forecast', label: 'AI Forecast', icon: 'chart' },
      { to: '/risk', label: 'Risk Prediction', icon: 'shield' },
      { to: '/recommend', label: 'Recommendation Engine', icon: 'users' },
      { to: '/simulation', label: 'Simulation Lab', icon: 'beaker' },
    ],
  },
  {
    title: 'Operations',
    items: [
      { to: '/requests', label: 'Resource Requests', icon: 'clipboard' },
      { to: '/stock', label: 'Live Stock', icon: 'box' },
      { to: '/allocations', label: 'Allocation History', icon: 'truck' },
    ],
  },
  {
    title: 'AI Tools',
    items: [
      { to: '/nlp', label: 'NLP Console', icon: 'chat' },
      { to: '/anomaly', label: 'Anomaly Detection', icon: 'alert' },
      { to: '/explorer', label: 'Data Explorer', icon: 'database' },
      { to: '/logs', label: 'System Logs', icon: 'list' },
    ],
  },
];

export function Sidebar({ open, onClose, status }) {
  const closeButtonRef = useRef(null);
  const asideRef = useRef(null);

  // Escape closes the drawer on mobile — the original had no keyboard exit.
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    closeButtonRef.current?.focus();
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  return (
    <aside
      ref={asideRef}
      id="sidebar"
      data-open={open}
      className="sidebar-fixed glass-sidebar"
      aria-label="Main navigation"
    >
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-sand-200/80 px-5 dark:border-neutral-750/60">
        <Link to="/" className="group flex items-center gap-2.5" onClick={onClose}>
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-500 shadow-sm shadow-indigo-500/30 transition-shadow group-hover:shadow-indigo-500/50">
            <Icon name="bulb" className="h-4 w-4 text-white" strokeWidth={2.4} />
          </span>
          <span className="text-base font-bold tracking-tight text-sand-600 dark:text-white">
            ResNav
          </span>
          <span className="rounded border border-indigo-200 bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-indigo-700 dark:border-indigo-800/50 dark:bg-indigo-900/40 dark:text-indigo-400">
            AI
          </span>
        </Link>

        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-sand-400 hover:text-sand-600 dark:hover:text-neutral-200 lg:hidden"
          aria-label="Close navigation"
        >
          <Icon name="close" className="h-4 w-4" />
        </button>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <p className="sidebar-section-title">{section.title}</p>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`}
              >
                <Icon name={item.icon} className="h-4 w-4" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-sand-200/60 px-4 py-3 dark:border-neutral-750/60">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 text-xs font-bold text-white shadow">
            AI
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-sand-600 dark:text-neutral-200">
              ResNav AI
            </p>
            <p className="text-[10px] text-sand-400 dark:text-neutral-600">
              {status ? `Fulfilment ${status.fulfilment_rate}%` : 'Intelligence Platform'}
            </p>
          </div>
          <StatusDot level={status?.level} />
        </div>
      </div>
    </aside>
  );
}

function StatusDot({ level = 'nominal' }) {
  const tones = {
    nominal: { color: 'bg-emerald-500', label: 'All systems nominal' },
    busy: { color: 'bg-indigo-500', label: 'Dispatch queue active' },
    degraded: { color: 'bg-amber-500', label: 'Attention required' },
  };
  const tone = tones[level] ?? tones.nominal;
  return (
    <span className={`h-2 w-2 shrink-0 rounded-full ${tone.color} pulse`} title={tone.label}>
      <span className="sr-only">{tone.label}</span>
    </span>
  );
}
