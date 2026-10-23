import { Link } from 'react-router';
import { TYPE_LABEL, type DeviceType } from '../../api/devices';
import { useOverview, type Classification, type Overview } from '../../api/operations';
import { FillBar, IntakeChart, Kpi } from '../../components/charts';
import { Badge, PageHeader } from '../../components/ui';

const kg = (n: number) => `${Math.round(n * 10) / 10} kg`;
const peso = (n: number) => `₱${n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function OverviewPage() {
  const o = useOverview();
  const today = new Date().toLocaleDateString('en-PH', { weekday: 'long', month: 'long', day: 'numeric' });
  return (
    <>
      <PageHeader title="MRF overview" sub={`${today} · everything happening at the Barangay Sapul MRF`} />
      {o.isPending && <p className="text-muted">Loading…</p>}
      {o.isError && <p className="text-crit">{o.error.message}</p>}
      {o.data && <Dashboard o={o.data} />}
    </>
  );
}

function Dashboard({ o }: { o: Overview }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-4">
        <Kpi label="Received today" value={kg(o.today_kg)} sub={`${o.today_deliveries} deliveries`} />
        <Link to="/admin/approvals" className="rounded-xl hover:ring-2 hover:ring-leaf-300">
          <Kpi label="Pending approvals" value={String(o.pending_approvals)} sub="requests and reviews waiting" />
        </Link>
        <Kpi label="Segregation compliance" value={`${o.compliance_week_pct}%`} sub="last 7 days" />
        <Kpi label="In storage" value={kg(o.in_storage_kg)} sub={`${o.areas.length} storage areas`} />
        <Link to="/admin/operations/outgoing" className="rounded-xl hover:ring-2 hover:ring-leaf-300">
          <Kpi label="Income this month" value={peso(o.income_month)} sub="approved sales" />
        </Link>
      </div>
      <div className="grid grid-cols-[2fr_1fr] gap-4">
        <section aria-label="Waste received, last 14 days" className="rounded-xl border border-line bg-white p-4">
          <div className="mb-2 flex items-baseline">
            <h3 className="text-sm font-bold">Waste received (kg), last 14 days</h3>
            <Link to="/admin/operations/intake" className="ml-auto text-xs font-semibold text-leaf-700 underline">Intake records</Link>
          </div>
          <IntakeChart data={o.intake_14d} />
        </section>
        <CameraTile c={o.latest_classification} />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <section aria-label="Storage areas" className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-1 text-sm font-bold">Storage areas</h3>
          {o.areas.length ? o.areas.map((a) => <FillBar key={a.id} area={a} />) : <p className="text-sm text-ink-2">No storage areas yet.</p>}
        </section>
        <section aria-label="Compost batches" className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-1 text-sm font-bold">Compost batches</h3>
          {o.compost.length === 0 && <p className="text-sm text-ink-2">No active batches.</p>}
          <ul>
            {o.compost.map((b) => (
              <li key={b.id} className="flex items-center gap-2 border-b border-line/60 py-2 text-sm last:border-0">
                <span className="font-semibold">{b.code}</span>
                <span className="text-ink-2">Day {b.day}</span>
                <span className="ml-auto">{b.temp_c ?? '—'} °C · {b.moisture_pct ?? '—'}%</span>
                {b.in_range === false ? <Badge kind="crit">Out of range</Badge> : b.in_range ? <Badge kind="ok">In range</Badge> : <Badge kind="dash">No reading</Badge>}
              </li>
            ))}
          </ul>
        </section>
        <section aria-label="Devices" className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-1 text-sm font-bold">Devices</h3>
          {o.devices.length === 0 && <p className="text-sm text-ink-2">No devices registered.</p>}
          <ul>
            {o.devices.map((d) => (
              <li key={d.code} className="flex items-center gap-2 border-b border-line/60 py-2 text-sm last:border-0">
                <span className="font-semibold">{d.code}</span>
                <span className="truncate text-ink-2">{TYPE_LABEL[d.type as DeviceType]}</span>
                <span className="ml-auto">
                  {d.status === 'online' ? <Badge kind="ok">● Online</Badge> : d.status === 'offline' ? <Badge kind="crit">○ Offline</Badge> : <Badge kind="dash">Never</Badge>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

export function CameraTile({ c, large = false }: { c: Classification | null; large?: boolean }) {
  return (
    <section aria-label="Sorting area camera" className="flex flex-col overflow-hidden rounded-xl bg-[#14231c] text-white">
      <div className="flex items-center gap-3 bg-black/40 px-3 py-2 text-xs">
        <span className="flex items-center gap-1.5 font-bold tracking-wide"><span className="size-2 rounded-full bg-[#f04438]" />LATEST</span>
        <span>Sorting area camera</span>
        {!large && <Link to="/admin/operations/camera" className="ml-auto underline">Open live camera</Link>}
      </div>
      <div className={`relative flex-1 bg-cover bg-center ${large ? 'min-h-[420px]' : 'min-h-[200px]'}`}
        style={c?.image_url ? { backgroundImage: `linear-gradient(rgba(10,30,20,.15),rgba(10,30,20,.15)), url(${c.image_url})` } : undefined}>
        {c ? (
          <div className="absolute top-[28%] left-[33%] h-[46%] w-[32%] rounded-md border-[3px] border-white shadow-[0_0_0_9999px_rgba(10,30,20,.25)]">
            <b className="absolute -top-7 -left-[3px] rounded-md rounded-bl-none bg-leaf-700 px-2.5 py-0.5 text-xs whitespace-nowrap">
              {c.suggested} · {Math.round(c.confidence * 100)}%
            </b>
          </div>
        ) : (
          <p className="absolute inset-0 grid place-items-center text-sm">No camera results yet.</p>
        )}
      </div>
      {c && (
        <div className="bg-black/40 px-3 py-2 text-xs">
          {c.final ? (c.changed ? `Changed to ${c.final} by ${c.confirmed_by}` : `Confirmed ${c.final} by ${c.confirmed_by}`) : 'Waiting for the operator to confirm'}
          {' · '}
          {new Date(c.suggested_at).toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' })}
        </div>
      )}
    </section>
  );
}
