import { Link } from 'react-router';
import { useAcknowledge, useAlerts } from '../../api/alerts';
import { useMe } from '../../api/auth';
import { usePredictions } from '../../api/insights';
import { useIntake, useOutgoing, useOverview, useWaiting } from '../../api/operations';
import { FillBar, Kpi } from '../../components/charts';
import { btn } from '../../components/ui';
import { kg, when } from '../operations/shared';
import { DeliveryCard } from './IntakePage';
import { Card, touch } from './shared';

const greeting = (hour: number) => (hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening');
const clock = (iso: string) => new Date(iso).toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' });

export default function TodayPage() {
  const me = useMe().data;
  const o = useOverview();
  const toSeparate = useWaiting('segregation');
  const toSort = useWaiting('sorting');
  const today = useIntake(1);
  const alerts = useAlerts('open');
  const ack = useAcknowledge();
  const outgoing = useOutgoing(30);
  const pendingOut = outgoing.data?.pending;
  const forecast = usePredictions(0);
  const predictions = forecast.data;
  const partFailed = [toSeparate, toSort, outgoing, forecast].find((q) => q.error)?.error;
  const fullest = predictions?.outlook.find((a) => a.days_to_full !== null); // soonest first from the API
  // The forecast list starts at today, so pick the first later day.
  const tomorrow = predictions?.forecast.find((f) => f.day > new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' }));

  const now = new Date();
  const waiting = toSeparate.data ?? [];
  const oldest = waiting[waiting.length - 1]; // the list comes newest first
  const dryKg = (toSort.data ?? []).reduce((sum, d) => sum + (d.segregation?.dry_kg ?? 0), 0);
  const alertKinds = Object.entries(o.data?.open_alerts ?? {});
  const count = (n: number | undefined, label: string) => (n === undefined ? '…' : `${n} ${label}`);

  const flow = [
    ['/op/intake', 'Intake', count(o.data?.today_deliveries, 'today')],
    ['/op/segregation', 'Segregation', count(o.data?.awaiting_segregation, 'waiting')],
    ['/op/sorting', 'Sorting', count(toSort.data?.length, 'waiting')],
    ['/op/storage', 'Storage', count(o.data?.areas.length, 'areas')],
    ['/op/compost', 'Compost', o.data ? `${kg(o.data.wet_waiting_kg)} wet waiting` : '…'],
    ['/op/outgoing', 'Outgoing', count(pendingOut, 'pending')],
  ] as const;

  return (
    <>
      <div>
        <h1 className="text-2xl font-extrabold">{greeting(now.getHours())}{me ? `, ${me.name.split(' ')[0]}` : ''}</h1>
        <p className="text-sm text-ink-2">{now.toLocaleDateString('en-PH', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
      </div>

      <nav aria-label="Daily work" className="grid grid-cols-3 gap-2">
        {flow.map(([to, label, sub]) => (
          <Link key={to} to={to} className={`${touch} rounded-lg border border-line bg-white px-2 py-1.5 text-sm font-semibold`}>
            {label}
            <small className="block font-normal text-ink-2">{sub}</small>
          </Link>
        ))}
      </nav>

      {o.isPending && <p className="text-muted">Loading…</p>}
      {o.error && <p role="alert" className="text-crit">{o.error.message}</p>}
      {!o.error && partFailed && <p role="alert" className="text-crit">Some of today's numbers didn't load: {partFailed.message}</p>}
      {o.data && (
        <div className="grid grid-cols-2 gap-2">
          <Kpi label="Deliveries today" value={String(o.data.today_deliveries)} sub={`${kg(o.data.today_kg)} received`} />
          <Kpi label="Waiting for segregation" value={String(o.data.awaiting_segregation)} sub={oldest ? `Oldest: ${when(oldest.received_at)}` : 'None waiting'} />
          <Kpi label="Waiting to sort" value={toSort.data ? String(toSort.data.length) : '…'} sub={toSort.data ? `${kg(dryKg)} dry waste` : undefined} />
          <Kpi label="Open alerts" value={String(alertKinds.reduce((sum, [, n]) => sum + (n ?? 0), 0))}
            sub={alertKinds.map(([kind, n]) => `${n} ${kind}`).join(' · ') || 'None open'} />
        </div>
      )}

      {oldest && (
        <section aria-label="Next" className="rounded-xl bg-leaf-100 p-3 text-sm">
          <p>
            <b>Next:</b> {waiting.length === 1 ? '1 delivery is' : `${waiting.length} deliveries are`} waiting for a segregation check.
            {' '}Start with {oldest.code} ({oldest.source_area}, {clock(oldest.received_at)}).
          </p>
          <Link to="/op/segregation" className={`${btn.base} ${btn.primary} ${touch} mt-2 w-full`}>Go to segregation</Link>
        </section>
      )}

      <h2 className="text-lg font-bold">Today’s deliveries</h2>
      <ul aria-label="Today’s deliveries" className="flex flex-col gap-2">
        {today.isPending && <li className="text-muted">Loading…</li>}
        {today.error && <li role="alert" className="text-crit">{today.error.message}</li>}
        {today.data?.length === 0 && <li className="text-muted">No deliveries yet today.</li>}
        {today.data?.slice(0, 6).map((d) => <DeliveryCard key={d.id} d={d} />)}
      </ul>
      <Link to="/op/intake" className={`${btn.base} ${btn.secondary} ${touch} w-full`}>All deliveries</Link>

      <h2 className="text-lg font-bold">Alerts</h2>
      <ul aria-label="Alerts" className="flex flex-col gap-2">
        {alerts.isPending && <li className="text-muted">Loading…</li>}
        {alerts.error && <li role="alert" className="text-crit">{alerts.error.message}</li>}
        {alerts.data?.length === 0 && <li className="text-muted">No open alerts.</li>}
        {alerts.data?.slice(0, 3).map((a) => (
          <Card key={a.id} label={a.title}>
            <b className="block">{a.title}</b>
            <p className="text-xs text-muted">{a.details && `${a.details} · `}{when(a.opened_at)}</p>
            {!a.acknowledged_at && (
              <button className={`${btn.base} ${btn.primary} ${touch} mt-2 w-full`} disabled={ack.isPending} onClick={() => ack.mutate(a.id)}>
                Acknowledge
              </button>
            )}
          </Card>
        ))}
      </ul>
      {ack.error && <p role="alert" className="text-sm text-crit">{ack.error.message}</p>}
      <Link to="/op/alerts" className={`${btn.base} ${btn.secondary} ${touch} w-full`}>All alerts</Link>

      {o.data && (
        <>
          <h2 className="text-lg font-bold">Storage areas</h2>
          <section aria-label="Storage areas" className="rounded-xl border border-line bg-white px-3 py-2">
            {o.data.areas.length === 0 && <p className="text-muted">No storage areas set up.</p>}
            {o.data.areas.map((a) => <FillBar key={a.id} area={a} />)}
            {predictions?.ready && (fullest || tomorrow) && (
              <p className="mt-2 text-sm">
                <b>Predicted:</b> {[fullest && (fullest.days_to_full === 0 ? `${fullest.area} is full now` : `${fullest.area} full in ~${fullest.days_to_full} days`), tomorrow && `tomorrow ~${Math.round(tomorrow.kg)} kg intake`].filter(Boolean).join(' · ')}
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
