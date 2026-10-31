import { Link } from 'react-router';
import { useMyAccess } from '../../api/access';
import { useAlerts } from '../../api/alerts';
import { usePredictions } from '../../api/insights';
import { useOverview, type Overview } from '../../api/operations';
import { FillBar, ForecastChart, IntakeChart, Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { kg, when } from '../operations/shared';

export default function OverviewPage() {
  const o = useOverview();
  const grants = useMyAccess().data?.grants;
  return (
    <>
      <PageHeader title="MRF overview" sub="View only." />
      {o.isPending && <p className="text-muted">Loading…</p>}
      {o.error && <p role="alert" className="text-crit">{o.error.message}</p>}
      {o.data && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi label="Received today" value={kg(o.data.today_kg)} sub={`${o.data.today_deliveries} deliveries`} />
            <Kpi label="Segregation compliance" value={o.data.compliance_week_pct === null ? '—' : `${o.data.compliance_week_pct}%`}
              sub={o.data.compliance_week_pct === null ? 'Not available' : 'Last 7 days'} />
            <Kpi label="In storage" value={kg(o.data.in_storage_kg)} sub={`${o.data.areas.length} storage areas`} />
            <Kpi label="Active compost batches" value={String(o.data.active_batches)} />
          </div>
          <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
            <section aria-label="Waste received, last 14 days" className="rounded-xl border border-line bg-white p-4">
              <div className="mb-2 flex items-baseline">
                <h3 className="text-sm font-bold">Waste received (kg), last 14 days</h3>
                <Link to="/staff/records" className="ml-auto text-xs font-semibold text-leaf-700 underline">Records</Link>
              </div>
              {grants?.predictions ? <WithForecast o={o.data} /> : <IntakeChart data={o.data.intake_14d} />}
            </section>
            <div className="flex flex-col gap-4">
              {grants?.alerts && <Notifications />}
              <section aria-label="Storage areas" className="rounded-xl border border-line bg-white p-4">
                <h3 className="mb-1 text-sm font-bold">Storage areas</h3>
                {o.data.areas.length ? o.data.areas.map((a) => <FillBar key={a.id} area={a} />) : <p className="text-sm text-ink-2">No storage areas yet.</p>}
              </section>
            </div>
          </div>
        </>
      )}
    </>
  );
}

/** Hatched forecast days once the model has enough records; the plain chart until then. */
function WithForecast({ o }: { o: Overview }) {
  const p = usePredictions(0).data;
  if (!p?.ready || !p.forecast.length) return <IntakeChart data={o.intake_14d} />;
  return (
    <>
      <ForecastChart actual={o.intake_14d} forecast={p.forecast} />
      <p className="text-xs text-muted">kg per day · hatched = forecast</p>
    </>
  );
}

function Notifications() {
  const alerts = useAlerts('open');
  return (
    <section aria-label="Notifications" className="rounded-xl border border-line bg-white p-4">
      <div className="mb-1 flex items-baseline">
        <h3 className="text-sm font-bold">Notifications</h3>
        <Link to="/staff/notifications" className="ml-auto text-xs font-semibold text-leaf-700 underline">See all</Link>
      </div>
      {alerts.isPending && <p className="text-sm text-muted">Loading…</p>}
      {alerts.error && <p role="alert" className="text-sm text-crit">{alerts.error.message}</p>}
      {alerts.data?.length === 0 && <p className="text-sm text-ink-2">No open alerts.</p>}
      <ul>
        {alerts.data?.slice(0, 3).map((a) => (
          <li key={a.id} className="flex justify-between gap-2 border-b border-line/60 py-2 text-sm last:border-0">
            <span>{a.title}</span>
            <span className="whitespace-nowrap text-xs text-muted">{when(a.opened_at)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
