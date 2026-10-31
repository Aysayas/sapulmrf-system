import { PageLoad } from '../components/PageLoad';
import { NavLink, Outlet, useNavigate } from 'react-router';
import { ROLE_LABEL, useLogout, useMe } from '../api/auth';

const NAV = [
  { to: '/staff', label: 'Overview', end: true },
  { to: '/staff/records', label: 'Records' },
  { to: '/staff/reports', label: 'Reports' },
  { to: '/staff/notifications', label: 'Notifications' },
];

/** The view-only staff shell: same dark-green sidebar as admin on a laptop; it stacks on a phone. */
export default function StaffLayout() {
  const me = useMe().data!;
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <div className="grid min-h-screen md:grid-cols-[232px_1fr]">
      <aside className="flex flex-col gap-0.5 bg-leaf-900 px-3 py-4 text-[#e3efe7]">
        <div className="flex items-center gap-2.5 px-2 pb-3.5">
          <span className="grid size-[30px] place-items-center rounded-lg bg-leaf-600 text-[11px] font-bold text-white">MRF</span>
          <div className="font-bold">
            SapulMRF<small className="block text-[11px] font-normal text-[#9dbfab]">Barangay Sapul MRF</small>
          </div>
        </div>
        <nav aria-label="Staff">
          {NAV.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              end={i.end}
              className={({ isActive }) => `flex items-center rounded-md p-2 font-medium ${isActive ? 'bg-leaf-100 font-bold text-leaf-900' : 'hover:bg-white/10'}`}
            >
              {i.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="flex h-14 items-center justify-end gap-3 border-b border-line bg-white px-4">
          <span className="min-w-0 truncate text-right text-sm leading-tight">
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
        <main className="flex flex-1 flex-col gap-4 p-4 md:p-6">
          <PageLoad><Outlet /></PageLoad>
        </main>
      </div>
    </div>
  );
}
