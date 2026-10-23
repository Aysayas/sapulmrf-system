import { NavLink, Outlet } from 'react-router';
import { PageHeader } from '../../components/ui';

const TABS = [
  ['users', 'Users'],
  ['roles', 'Roles and permissions'],
  ['masterdata', 'Master data'],
  ['devices', 'IoT devices'],
  ['ranges', 'Ranges and limits'],
  ['activity', 'Activity log'],
] as const;

export default function SettingsLayout() {
  return (
    <>
      <PageHeader title="Settings" />
      <nav aria-label="Settings" className="flex gap-1 border-b border-line">
        {TABS.map(([path, label]) => (
          <NavLink
            key={path}
            to={`/admin/settings/${path}`}
            className={({ isActive }) =>
              `-mb-px border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${isActive ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  );
}
