import { PageLoad } from '../components/PageLoad';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { useAlertSummary } from '../api/alerts';
import { ROLE_LABEL, useLogout, useMe } from '../api/auth';

const TABS = [
  ['/op/today', 'Today'],
  ['/op/intake', 'Intake'],
  ['/op/sorting', 'Sort'],
  ['/op/storage', 'Storage'],
  ['/op/more', 'More'],
] as const;

/** The operator shell, phone first: top bar, one column, tab bar at the bottom. On a laptop it stays a centred column. */
export default function OperatorLayout() {
  const me = useMe().data!;
  const logout = useLogout();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // Every screen outside the first four tabs is reached through More.
  const inMainTab = TABS.slice(0, 4).some(([to]) => pathname.startsWith(to));
  const alerts = useAlertSummary().data?.unacknowledged ?? 0;

  return (
    <div className="mx-auto flex min-h-screen max-w-[480px] flex-col bg-surface">
      <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-line bg-white px-4">
        <span className="grid size-8 place-items-center rounded-lg bg-leaf-700 text-[11px] font-bold text-white">MRF</span>
        <span className="min-w-0 flex-1 truncate text-sm leading-tight">
          <b>{me.name}</b>
          <small className="block text-xs text-muted">{ROLE_LABEL[me.role]}</small>
        </span>
        <button
          className="min-h-11 rounded-lg border border-edge px-3 text-sm font-semibold"
          onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })}
        >
          Log out
        </button>
      </header>
      <main className="flex flex-1 flex-col gap-4 px-4 pt-4 pb-[calc(6rem+env(safe-area-inset-bottom))]">
        <PageLoad><Outlet /></PageLoad>
      </main>
      <nav aria-label="Operator" className="fixed bottom-0 pb-[env(safe-area-inset-bottom)] left-1/2 z-10 grid w-full max-w-[480px] -translate-x-1/2 grid-cols-5 border-t border-line bg-white">
        {TABS.map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `flex min-h-14 items-center justify-center gap-1.5 text-sm font-semibold ${(label === 'More' ? !inMainTab : isActive) ? 'bg-leaf-100 text-leaf-900' : 'text-ink-2'}`}
          >
            {label}
            {label === 'More' && alerts > 0 && (
              <span className="rounded-full bg-crit px-2 text-xs font-bold text-white">{alerts}<span className="sr-only"> not acknowledged</span></span>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
