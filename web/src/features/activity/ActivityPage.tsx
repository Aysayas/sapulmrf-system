import { useState } from 'react';
import { useActivity } from '../../api/activity';
import { useUsers } from '../../api/users';
import { inputCls } from '../../components/ui';

const PERIODS = [
  ['Today', 1],
  ['This week', 7],
  ['This month', 31],
  ['All', 0],
] as const;

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

export default function ActivityPage() {
  const [days, setDays] = useState<number>(7);
  const [userId, setUserId] = useState<number>(0);
  const users = useUsers();
  const activity = useActivity({ days: days || undefined, userId: userId || undefined });

  return (
    <>
      <div className="flex items-center gap-3">
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
        <select aria-label="User" className={`${inputCls} ml-auto w-56`} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
          <option value={0}>All users</option>
          {users.data?.map((u) => (
            <option key={u.id} value={u.id}>{u.name}</option>
          ))}
        </select>
      </div>
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
