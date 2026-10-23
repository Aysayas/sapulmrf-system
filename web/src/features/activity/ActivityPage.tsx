import { useState } from 'react';
import { activityQuery, useActivity, type ActivityCategory } from '../../api/activity';
import { download } from '../../api/client';
import { useUsers } from '../../api/users';
import { btn, inputCls } from '../../components/ui';

const PERIODS = [
  ['Today', 1],
  ['This week', 7],
  ['This month', 31],
  ['All', 0],
  ['Custom', -1],
] as const;
const CATEGORIES: [ActivityCategory, string][] = [
  ['', 'All actions'], ['logins', 'Logins'], ['users', 'Users and access'], ['approvals', 'Approvals and reviews'],
  ['reports', 'Reports'], ['records', 'Records and setup'],
];

const fieldCls = inputCls.replace('w-full', 'w-auto'); // the filters sit side by side and wrap
const when = (iso: string) =>
  new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

export default function ActivityPage() {
  const [days, setDays] = useState<number>(7);
  const [userId, setUserId] = useState<number>(0);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [category, setCategory] = useState<ActivityCategory>('');
  const [exportError, setExportError] = useState<string | null>(null);
  const users = useUsers();
  const custom = days === -1;
  const filters = { days: days > 0 ? days : undefined, userId: userId || undefined, category,
    from: custom ? from : undefined, to: custom ? to : undefined };
  const activity = useActivity(filters);
  const exportCsv = () => {
    setExportError(null);
    download(`/activity/export?${activityQuery(filters)}`).catch((e: Error) => setExportError(e.message));
  };

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Period" className="inline-flex overflow-hidden rounded-lg border border-leaf-700">
          {PERIODS.map(([label, d]) => (
            <button
              key={label}
              aria-pressed={days === d}
              onClick={() => setDays(d)}
              className={`border-r border-leaf-700 px-3.5 py-1.5 text-sm font-semibold last:border-r-0 ${days === d ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`}
            >
              {label}
            </button>
          ))}
        </div>
        {custom && (
          <>
            <input type="date" aria-label="From" className={`${fieldCls}`} value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} />
            <span className="text-sm text-muted">to</span>
            <input type="date" aria-label="To" className={`${fieldCls}`} value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} />
          </>
        )}
        <select aria-label="Action" className={`${fieldCls} ml-auto`} value={category} onChange={(e) => setCategory(e.target.value as ActivityCategory)}>
          {CATEGORIES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
        <select aria-label="User" className={`${fieldCls}`} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
          <option value={0}>All users</option>
          {users.data?.map((u) => (
            <option key={u.id} value={u.id}>{u.name}</option>
          ))}
        </select>
        <button className={`${btn.base} ${btn.secondary}`} onClick={exportCsv}>Export CSV</button>
      </div>
      {exportError && <p role="alert" className="text-sm text-crit">{exportError}</p>}
      {activity.data?.length === 100 && <p className="text-xs text-muted">Showing the latest 100. Export CSV has every matching row.</p>}
      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              {['When', 'Who', 'Action', 'Record'].map((h) => (
                <th key={h} className="px-3 py-2 font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {activity.isPending && <tr><td colSpan={4} className="px-3 py-4 text-muted">Loading…</td></tr>}
            {activity.isError && <tr><td colSpan={4} className="px-3 py-4 text-crit">{activity.error.message}</td></tr>}
            {activity.data?.length === 0 && <tr><td colSpan={4} className="px-3 py-4 text-muted">Nothing recorded for this filter.</td></tr>}
            {activity.data?.map((a) => (
              <tr key={a.id} className="border-b border-line/60 last:border-0">
                <td className="px-3 py-2.5 whitespace-nowrap text-ink-2">{when(a.at)}</td>
                <td className="px-3 py-2.5">{a.who}</td>
                <td className="px-3 py-2.5 font-semibold">{a.action}</td>
                <td className="px-3 py-2.5 text-ink-2">{a.record || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
