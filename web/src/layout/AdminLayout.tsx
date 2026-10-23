import { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { useApprovals } from '../api/approvals';
import { ROLE_LABEL, useLogout, useMe } from '../api/auth';

const NAV = [
  { section: 'Monitor', items: [{ to: '/admin', label: 'Overview', end: true }, { to: '/admin/approvals', label: 'Approvals' }, { to: '/admin/operations', label: 'Operations', sub: [
    ['intake', 'Intake'], ['segregation', 'Segregation'], ['sorting', 'Sorting'], ['inventory', 'Inventory'], ['compost', 'Compost'], ['outgoing', 'Outgoing'], ['camera', 'Live camera'],
  ] }] },
  { section: 'Analyze', items: [{ to: '/admin/insights', label: 'Insights' }] },
  { section: 'Manage', items: [{ to: '/admin/settings', label: 'Settings' }] },
];

/** The admin shell from the approved mockup: dark-green sidebar, top bar with the user menu. */
export default function AdminLayout() {
  const me = useMe().data!;
  const logout = useLogout();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const counts = useApprovals().data?.counts;
  const waiting = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  const [menu, setMenu] = useState(false);
  const initials = me.name.split(' ').map((w) => w[0]).slice(0, 2).join('');

  return (
    <div className="grid min-h-screen grid-cols-[232px_1fr]">
      <aside className="flex flex-col gap-0.5 bg-leaf-900 px-3 py-4 text-[#e3efe7]">
        <div className="flex items-center gap-2.5 px-2 pb-3.5">
          <span className="grid size-[30px] place-items-center rounded-lg bg-leaf-600 text-[11px] font-bold text-white">MRF</span>
          <div className="font-bold">
            SapulMRF<small className="block text-[11px] font-normal text-[#9dbfab]">Barangay Sapul MRF</small>
          </div>
        </div>
        {NAV.map((g) => (
          <nav key={g.section} aria-label={g.section}>
            <div className="px-2 pt-3.5 pb-1.5 text-xs font-semibold text-[#9dbfab]">{g.section}</div>
            {g.items.map((i) => (
              <div key={i.to}>
                <NavLink
                  to={i.to}
                  end={i.end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-md p-2 font-medium ${isActive && !i.sub ? 'bg-leaf-100 font-bold text-leaf-900' : isActive ? 'font-bold' : 'hover:bg-white/10'}`
                  }
                >
                  <span className="size-4 rounded border-[1.5px] border-current opacity-70" aria-hidden />
                  {i.label}
                  {i.to === '/admin/approvals' && waiting > 0 && (
                    <span className="ml-auto rounded-full bg-leaf-600 px-2 text-xs font-bold text-white" aria-label={`${waiting} waiting`}>{waiting}</span>
                  )}
                </NavLink>
                {i.sub && pathname.startsWith(i.to) &&
                  i.sub.map(([path, label]) => (
                    <NavLink
                      key={path}
                      to={`${i.to}/${path}`}
                      className={({ isActive }) =>
                        `my-0.5 ml-6 block rounded-md px-2 py-1.5 text-sm ${isActive ? 'bg-leaf-100 font-bold text-leaf-900' : 'hover:bg-white/10'}`
                      }
                    >
                      {label}
                    </NavLink>
                  ))}
              </div>
            ))}
          </nav>
        ))}
        <div className="mt-auto px-2 text-[11px] text-[#9dbfab]">SapulMRF · v0.1</div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="relative flex h-14 items-center gap-4 border-b border-line bg-white px-6">
          <span className="text-sm text-muted">Barangay Sapul MRF</span>
          <button
            className="ml-auto flex items-center gap-2 rounded-lg px-2 py-1 text-left text-xs hover:bg-surface"
            aria-label={`Account menu for ${me.name}`}
            aria-haspopup="menu"
            aria-expanded={menu}
            onClick={() => setMenu((m) => !m)}
          >
            <span className="grid size-[30px] place-items-center rounded-full bg-leaf-100 text-[11px] font-bold text-leaf-700">{initials}</span>
            <span>
              {me.name}
              <small className="block text-[11px] text-muted">{ROLE_LABEL[me.role]}</small>
            </span>
            <span aria-hidden>▾</span>
          </button>
          {menu && (
            <div role="menu" className="absolute top-12 right-6 z-10 w-56 rounded-xl bg-white p-2 shadow-xl ring-1 ring-line">
              <button
                role="menuitem"
                className="w-full rounded-md px-3 py-2 text-left font-semibold hover:bg-surface"
                onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })}
              >
                Log out
              </button>
            </div>
          )}
        </header>
        <main className="flex flex-1 flex-col gap-4 px-6 py-5">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
