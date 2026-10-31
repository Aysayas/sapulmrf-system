import { useState } from 'react';
import { useMyActivity } from '../../api/activity';
import { inputCls, PageHeader } from '../../components/ui';
import { when } from '../operations/shared';
import { Card, Field, touch } from './shared';

// The API counts back from now, so these are rolling windows rather than calendar days.
const PERIODS = [['24 hours', 1], ['7 days', 7], ['30 days', 30]] as const;

export default function HistoryPage() {
  const [days, setDays] = useState<number>(7);
  const [action, setAction] = useState('');
  const log = useMyActivity(days);
  // shortcut: the API returns the newest 100 rows, add paging if an operator ever passes that in a period.
  const actions = [...new Set(log.data?.map((a) => a.action))].sort();
  const rows = log.data?.filter((a) => !action || a.action === action);

  return (
    <>
      <PageHeader title="My history" sub="Everything you recorded, newest first." />
      <div role="group" aria-label="Period" className="grid grid-cols-3 overflow-hidden rounded-lg border border-leaf-700">
        {PERIODS.map(([label, d]) => (
          <button key={d} aria-pressed={days === d} onClick={() => { setDays(d); setAction(''); }}
            className={`${touch} border-r border-leaf-700 text-sm font-semibold last:border-r-0 ${days === d ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`}>
            {label}
          </button>
        ))}
      </div>
      <Field label="Action">
        <select className={`${inputCls} ${touch}`} value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">All actions</option>
          {actions.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </Field>
      {log.isPending && <p className="text-muted">Loading…</p>}
      {log.error && <p role="alert" className="text-crit">{log.error.message}</p>}
      <ul aria-label="My history" className="flex flex-col gap-2">
        {rows?.length === 0 && <li className="text-muted">Nothing recorded in this period.</li>}
        {rows?.map((a) => (
          <Card key={a.id} label={a.action}>
            <b>{a.action}</b>
            {a.record && <p className="text-sm text-ink-2">{a.record}</p>}
            <p className="text-xs text-muted">{when(a.at)}</p>
          </Card>
        ))}
      </ul>
    </>
  );
}
