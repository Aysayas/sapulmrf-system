import { useState } from 'react';
import { useAlerts } from '../../api/alerts';
import { PageHeader } from '../../components/ui';
import { Period, when } from '../operations/shared';
import { Granted } from './shared';

const STATES = [['Open', 'open'], ['Acknowledged', 'acknowledged'], ['Resolved', 'resolved']] as const;
type State = (typeof STATES)[number][1];

export default function NotificationsPage() {
  return (
    <>
      <PageHeader title="Notifications" sub="Compost out of range, disconnected devices and full storage areas." />
      <Granted screen="alerts" what="notifications"><Alerts /></Granted>
    </>
  );
}

function Alerts() {
  const [state, setState] = useState<State>('open');
  const alerts = useAlerts(state);
  return (
    <>
      <Period value={state} options={STATES} onChange={setState} />
      {alerts.error && <p role="alert" className="text-sm text-crit">{alerts.error.message}</p>}
      <ul aria-label="Notifications" className="rounded-xl border border-line bg-white px-4 [&>li]:py-3">
        {alerts.isPending && <li className="text-muted">Loading…</li>}
        {alerts.data?.length === 0 && <li className="text-muted">No {state} notifications.</li>}
        {alerts.data?.map((a) => (
          <li key={a.id} className="flex flex-wrap items-baseline justify-between gap-x-4 border-b border-line/60 last:border-0">
            <span><b>{a.title}</b> · <span className="text-sm text-ink-2">{a.details}</span></span>
            <span className="whitespace-nowrap text-xs text-muted">{when(a.opened_at)}</span>
          </li>
        ))}
      </ul>
    </>
  );
}
