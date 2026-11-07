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
      <div className="flex h-[72px] shrink-0 items-center justify-between px-5">
        <Link to="/" className="group flex items-center gap-3" onClick={onClose}>
          <span className="g-mark" aria-hidden="true">
            <Icon name="bulb" className="h-[18px] w-[18px]" strokeWidth={2.2} />
          </span>
          <span className="flex flex-col leading-none">
            <span className="g-display text-[0.9375rem] font-semibold text-[var(--rn-text)]">
              ResNav
            </span>
            <span className="mt-1 text-[0.625rem] font-medium tracking-[0.14em] text-[var(--rn-text-3)]">
              RELIEF LOGISTICS
            </span>
          </span>
        </Link>

        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          className="rounded-full p-1.5 text-[var(--rn-text-3)] transition-colors hover:text-[var(--rn-text)] lg:hidden"
          aria-label="Close navigation"
        >
          <Icon name="close" className="h-4 w-4" />
        </button>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto overflow-x-hidden pb-3">
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

      <div className="shrink-0 p-3">
        <div className="g-thin flex items-center gap-3 px-3 py-2.5">
          <StatusDot level={status?.level} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[0.6875rem] font-semibold text-[var(--rn-text)]">
              {status?.level === 'degraded'
                ? 'Attention required'
                : status?.level === 'busy'
                  ? 'Dispatch in progress'
                  : 'All systems nominal'}
            </p>
            <p className="text-[0.625rem] text-[var(--rn-text-3)]">
              {status ? `${status.fulfilment_rate}% fulfilment` : 'connecting…'}
            </p>
          </div>
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
