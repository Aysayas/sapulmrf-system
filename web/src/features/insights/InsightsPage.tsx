import { useState } from 'react';
import { Link } from 'react-router';
import { MODEL_LABEL, usePredictions, type Camera, type Predictions } from '../../api/insights';
import { ForecastChart, Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { kg, Table } from '../operations/shared';

const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' });
const pctOrDash = (n: number | null) => (n === null ? '—' : `${n}%`);

export default function InsightsPage() {
  const [category, setCategory] = useState(0);
  const p = usePredictions(category);
  return (
    <>
      <PageHeader title="Predictions" sub="Forecasts from your own MRF records. Use them to plan; they are not exact." />
      {p.isPending && <p className="text-muted">Loading…</p>}
      {p.error && <p className="text-crit">{p.error.message}</p>}
      {p.data && !p.data.ready && <NotReady p={p.data} />}
      {p.data?.ready && <Ready p={p.data} category={category} setCategory={setCategory} />}
    </>
  );
}

function NotReady({ p }: { p: Predictions }) {
  const pct = Math.min(100, Math.round((p.days_of_records / p.min_days) * 100));
  return (
    <section aria-label="Not enough data yet" className="max-w-xl rounded-xl border border-line bg-white p-6">
      <h3 className="text-lg font-bold">Predictions start after {p.min_days} days of records</h3>
      <p className="mt-1 text-sm text-ink-2">You have {p.days_of_records} {p.days_of_records === 1 ? 'day' : 'days'} so far. Keep recording every delivery, even on manual entry.</p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={p.days_of_records} aria-valuemin={0} aria-valuemax={p.min_days} aria-label="Days of records">
        <div className="h-full rounded-full bg-leaf-600" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-xs text-muted">
        {p.days_of_records} of {p.min_days} days · change the minimum in <Link className="underline" to="/admin/settings/ranges">Settings › Ranges and limits</Link>
      </p>
    </section>
  );
}

function Ready({ p, category, setCategory }: { p: Predictions; category: number; setCategory: (n: number) => void }) {
  const other = p.model_used === 'ml' ? 'baseline' : 'ml';
  return (
    <>
      <div role="tablist" aria-label="Waste category" className="flex flex-wrap gap-1 border-b border-line">
        {p.categories.map((c) => (
          <button key={c.id} role="tab" aria-selected={category === c.id} onClick={() => setCategory(c.id)}
            className={`-mb-px border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${category === c.id ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`}>
            {c.name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-[2fr_1fr] gap-4">
        <section aria-label="Waste intake forecast" className="rounded-xl border border-line bg-white p-4">
          <div className="mb-2 flex flex-wrap items-baseline gap-x-3">
            <h3 className="text-sm font-bold">Waste intake forecast, next 7 days (kg)</h3>
            <span className="text-xs text-muted">
              Based on {p.days_of_records} days of records{p.made_on ? ` · made ${dayLabel(p.made_on)}` : ''}
            </span>
            <span className="ml-auto flex items-center gap-3 text-xs text-ink-2" aria-hidden>
              <span className="flex items-center gap-1"><span className="size-3 rounded-sm bg-leaf-600" />actual</span>
              <span className="flex items-center gap-1">
                <span className="size-3 rounded-sm border border-leaf-600 bg-[repeating-linear-gradient(45deg,#2e8b5e_0_2px,#ddefe3_2px_5px)]" />predicted
              </span>
            </span>
          </div>
          {p.forecast.length ? <ForecastChart actual={p.history} forecast={p.forecast} />
            : <p className="py-16 text-center text-sm text-ink-2">Today's forecast hasn't been made yet. The worker makes it once a day.</p>}
        </section>

        <section aria-label="Forecast model" className="flex flex-col gap-3 rounded-xl border border-line bg-white p-4">
          <h3 className="text-sm font-bold">Forecast model</h3>
          <div>
            <div className="text-xs text-ink-2">Using</div>
            <div className="text-lg font-extrabold">{MODEL_LABEL[p.model_used]}</div>
            <div className="text-sm text-ink-2">
              Off by {pctOrDash(p.errors_14d[p.model_used])} of the total kg over the last 14 days, predicting 1 day ahead
              ({MODEL_LABEL[other].split(' (')[0].toLowerCase()}: {pctOrDash(p.errors_14d[other])})
            </div>
          </div>
          <table aria-label="Model errors" className="text-sm">
            <thead><tr className="text-left text-xs text-muted"><th className="font-semibold">Total kg off</th><th className="font-semibold">7 days</th><th className="font-semibold">14 days</th></tr></thead>
            <tbody>
              {(['ml', 'baseline'] as const).map((m) => (
                <tr key={m} className={m === p.model_used ? 'font-bold' : ''}>
                  <td className="py-1">{MODEL_LABEL[m].split(' (')[0]}</td><td>{pctOrDash(p.errors_7d[m])}</td><td>{pctOrDash(p.errors_14d[m])}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-auto text-xs text-muted">
            Both models forecast every day from the records before it. The one that was closer in total kg on days 8–14 back
            is used, so the last 7 days are a fair test of that choice.
          </p>
        </section>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <section aria-label="Storage outlook" className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-1 text-sm font-bold">Storage outlook</h3>
          <ul>
            {p.outlook.map((o) => (
              <li key={o.area} className="flex items-center gap-2 border-b border-line/60 py-2 text-sm last:border-0">
                <span>{o.area}</span>
                <span className="whitespace-nowrap text-ink-2">{o.pct}% now</span>
                <span className={`ml-auto whitespace-nowrap ${o.days_to_full !== null && o.days_to_full <= 7 ? 'font-bold text-warn' : 'text-ink-2'}`}>
                  {o.days_to_full === null || o.days_to_full > 30 ? '30+ days' : o.days_to_full === 0 ? 'Full now' : `Full in ~${o.days_to_full} days`}
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section aria-label="Suggested pickup or sale schedule" className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-1 text-sm font-bold">Suggested pickup or sale</h3>
          {p.schedule.length === 0 && <p className="text-sm text-ink-2">No area reaches its alert level in the next 14 days.</p>}
          <ul>
            {p.schedule.map((s) => (
              <li key={s.on + s.what} className="border-b border-line/60 py-2 text-sm last:border-0">
                <span className="font-bold">{dayLabel(s.on)}</span> · {s.what}
                <span className="block text-xs text-muted">{s.why}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">A plan only. The operator still records each sale or pickup for approval.</p>
        </section>
        {p.camera && <section aria-label="Camera accuracy summary" className="flex flex-col gap-3">
          <Kpi label="Camera suggestions kept" value={p.camera.confirmed ? `${p.camera.kept_pct}%` : '—'}
            sub={p.camera.confirmed ? `${p.camera.kept} of ${p.camera.confirmed} in the last 30 days` : 'No camera results in the last 30 days'} />
          <Kpi label="Operator changes marked wrong" value={String(p.camera.reviewed_wrong)} sub={`of ${p.camera.changed} changes, from your reviews`} />
        </section>}
      </div>

      {p.camera && (p.camera.confirmed > 0 || p.camera.kiosk) && <CameraAccuracy c={p.camera} />}

      <section aria-label="Predicted vs actual" className="flex flex-col gap-2">
        <div className="flex items-baseline gap-3">
          <h3 className="text-sm font-bold">Predicted vs actual</h3>
          <span className="text-xs text-muted">each day's forecast was made before the day, by the model in use</span>
          {p.avg_error_pct !== null && <span className="ml-auto text-sm font-bold">7-day average, 1 day ahead: {p.avg_error_pct}% off</span>}
        </div>
        {p.missing_days > 0 && (
          <p className="text-xs text-muted">
            {p.missing_days} of the last 7 days have no forecast: the system was off those days. The worker fills in up to
            14 missed days when it starts again.
          </p>
        )}
        <Table label="Predicted vs actual" head={['Day', 'Predicted', 'Actual', 'Difference']}
          state={{ isPending: false, error: null, count: p.compared.length }} empty="No forecasts to compare yet.">
          {p.compared.map((c) => (
            <tr key={c.day}>
              <td className="font-semibold">{dayLabel(c.day)}</td>
              <td>{kg(c.predicted)}</td>
              <td>{kg(c.actual)}</td>
              <td>{c.diff > 0 ? '+' : c.diff < 0 ? '−' : ''}{kg(Math.abs(c.diff))}{c.pct !== null ? ` (${c.pct}%)` : ''}</td>
            </tr>
          ))}
        </Table>
      </section>
    </>
  );
}

/** How the camera is really doing, from what operators kept or changed, and from the kiosk's own category. */
function CameraAccuracy({ c }: { c: Camera }) {
  return (
    <section aria-label="Camera accuracy" className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="flex flex-col gap-2 lg:col-span-2">
        <h3 className="text-sm font-bold">Camera accuracy by material, last 30 days</h3>
        <p className="text-xs text-muted">What the camera suggested, and what operators kept or chose instead.</p>
        <Table label="Camera accuracy by material" head={['Camera said', 'Suggested', 'Kept', 'Changed', 'Most often changed to']}
          state={{ isPending: false, error: null, count: c.by_material.length }} empty="No confirmed suggestions yet.">
          {c.by_material.map((m) => (
            <tr key={m.material}>
              <td className="font-semibold">{m.material}</td><td>{m.suggested}</td>
              <td>{m.kept} ({Math.round((m.kept / m.suggested) * 100)}%)</td><td>{m.changed}</td><td>{m.changed_to ?? '—'}</td>
            </tr>
          ))}
        </Table>
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-bold">Is the camera's "% sure" right?</h3>
        <p className="text-xs text-muted">How often suggestions were kept at each confidence. Higher bands should be kept more.</p>
        <Table label="Camera confidence" head={['Camera was', 'Confirmed', 'Kept']}
          state={{ isPending: false, error: null, count: c.by_confidence.length }} empty="No confirmed suggestions yet.">
          {c.by_confidence.map((b) => (
            <tr key={b.band}><td className="font-semibold">{b.band} sure</td><td>{b.confirmed}</td><td>{b.kept_pct}%</td></tr>
          ))}
        </Table>
        {c.kiosk && (
          <p className="text-sm">
            <span className="font-bold">Kiosk category matched {c.kiosk.matched_pct}%</span>
            <span className="text-ink-2"> · {c.kiosk.matched} of {c.kiosk.with_camera} drop-offs were recorded as the kind the camera saw</span>
          </p>
        )}
      </div>
    </section>
  );
}
