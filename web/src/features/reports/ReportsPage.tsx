import { useState } from 'react';
import { useItems } from '../../api/masterdata';
import { narrativePath, useExportReport, useRecentReports, useReport, type ReportFormat, type ReportKind, type ReportParams } from '../../api/reports';
import { btn, inputCls, PageHeader, Toast } from '../../components/ui';
import { Table, when } from '../operations/shared';
import ReportFindings from './ReportFindings';

const KINDS: [ReportKind, string, string][] = [
  ['intake', 'Intake', 'Deliveries and weights per purok and category'],
  ['segregation', 'Segregation', 'Compliance per purok'],
  ['inventory', 'Inventory', 'Stock per material and area, as of now'],
  ['composting', 'Composting', 'Batches, readings, compost produced'],
  ['outgoing', 'Outgoing material', 'Sales, compost, residual'],
  ['income', 'Income', 'Income from recyclables and compost'],
];
const BY_AREA: ReportKind[] = ['intake', 'segregation'];

/** A Manila calendar day as YYYY-MM-DD, `back` days ago. */
const manilaDay = (back = 0) => new Date(Date.now() - back * 86_400_000).toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' });
const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' });

export default function ReportsPage() {
  const [form, setForm] = useState<ReportParams>({ kind: 'segregation', from: manilaDay(29), to: manilaDay(), area: 0 });
  const [shown, setShown] = useState<ReportParams | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const exp = useExportReport();
  const run = (p: ReportParams, format: ReportFormat, title: string) =>
    exp.mutate({ ...p, format }, { onSuccess: () => setDone(`${title} exported as ${format.toUpperCase()}`) });

  return (
    <>
      {shown ? <Preview p={shown} onBack={() => setShown(null)} onExport={run} busy={exp.isPending} />
        : <Choose form={form} setForm={setForm} onPreview={() => setShown(form)} onExport={run} />}
      {exp.error && <p role="alert" className="text-sm text-crit">{exp.error.message}</p>}
      <Toast message={done} />
    </>
  );
}

function Choose({ form, setForm, onPreview, onExport }: {
  form: ReportParams; setForm: (p: ReportParams) => void; onPreview: () => void; onExport: (p: ReportParams, f: ReportFormat, t: string) => void;
}) {
  const puroks = useItems('puroks');
  const recent = useRecentReports();
  const byArea = BY_AREA.includes(form.kind);
  const bad = !form.from || !form.to || form.to < form.from;
  return (
    <>
      <PageHeader title="Reports" sub="Pick a report and a date range." />
      <div role="radiogroup" aria-label="Report" className="grid grid-cols-3 gap-3">
        {KINDS.map(([k, label, sub]) => (
          <button key={k} role="radio" aria-checked={form.kind === k} onClick={() => setForm({ ...form, kind: k })}
            className={`rounded-xl border bg-white p-4 text-left ${form.kind === k ? 'border-leaf-700 ring-2 ring-leaf-700' : 'border-line hover:border-edge'}`}>
            <span className="block font-bold">{label}</span>
            <span className="text-sm text-ink-2">{sub}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-4">
        <label className="text-sm font-semibold">From
          <input type="date" className={`${inputCls} mt-1 w-44`} value={form.from} max={form.to} disabled={form.kind === 'inventory'}
            onChange={(e) => setForm({ ...form, from: e.target.value })} />
        </label>
        <label className="text-sm font-semibold">To
          <input type="date" className={`${inputCls} mt-1 w-44`} value={form.to} min={form.from} disabled={form.kind === 'inventory'}
            onChange={(e) => setForm({ ...form, to: e.target.value })} />
        </label>
        <label className="text-sm font-semibold">Source area
          <select className={`${inputCls} mt-1 w-48`} value={byArea ? form.area : 0} disabled={!byArea}
            onChange={(e) => setForm({ ...form, area: Number(e.target.value) })}>
            <option value={0}>All puroks</option>
            {puroks.data?.filter((p) => p.active).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <button className={`${btn.base} ${btn.primary} ml-auto`} disabled={bad} onClick={onPreview}>Preview report</button>
      </div>
      {form.kind === 'inventory' && <p className="-mt-2 text-xs text-muted">Inventory shows the stock now, so it has no date range.</p>}
      {!byArea && form.kind !== 'inventory' && <p className="-mt-2 text-xs text-muted">This report covers the whole MRF, not one purok.</p>}

      <h2 className="mt-2 text-lg font-bold">Recent reports</h2>
      <Table label="Recent reports" head={['Report', 'Range', 'Source area', 'Format', 'By', 'Created', '']}
        state={{ isPending: recent.isPending, error: recent.error, count: recent.data?.length }} empty="No reports exported yet.">
        {recent.data?.map((r) => (
          <tr key={r.id}>
            <td className="font-semibold">{r.title}</td>
            <td className="whitespace-nowrap">{r.kind === 'inventory' ? 'As of export' : `${dayLabel(r.from_day)} – ${dayLabel(r.to_day)}`}</td>
            <td>{BY_AREA.includes(r.kind) ? r.area : '—'}</td>
            <td>{r.format.toUpperCase()}</td>
            <td>{r.by}</td>
            <td className="whitespace-nowrap">{when(r.created_at)}</td>
            <td className="text-right">
              <button className={`${btn.base} ${btn.secondary} ${btn.small}`} title="Rebuilt from the current data"
                onClick={() => onExport({ kind: r.kind, from: r.from_day, to: r.to_day, area: r.area_id ?? 0 }, r.format, r.title)}>
                Download
              </button>
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}

function Preview({ p, onBack, onExport, busy }: {
  p: ReportParams; onBack: () => void; onExport: (p: ReportParams, f: ReportFormat, t: string) => void; busy: boolean;
}) {
  const r = useReport(p);
  const title = r.data?.title ?? 'Report';
  return (
    <>
      <PageHeader title={title} sub={r.data?.subtitle} actions={
        <>
          <button className={`${btn.base} ${btn.secondary}`} onClick={onBack}>Back</button>
          <button className={`${btn.base} ${btn.primary}`} disabled={!r.data || busy} onClick={() => onExport(p, 'pdf', title)}>Export PDF</button>
          <button className={`${btn.base} ${btn.primary}`} disabled={!r.data || busy} onClick={() => onExport(p, 'csv', title)}>Export CSV</button>
        </>
      } />
      {r.data && (
        <dl className="flex flex-wrap gap-3">
          {r.data.summary.map(([k, v]) => (
            <div key={k} className="min-w-36 rounded-xl border border-line bg-white px-4 py-3">
              <dt className="text-xs text-muted">{k}</dt>
              <dd className="text-xl font-extrabold">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {r.data && <ReportFindings findings={r.data.findings} narrative={narrativePath(p)} />}
      <Table label={title} head={r.data?.columns ?? []} state={{ isPending: r.isPending, error: r.error, count: r.data?.rows.length }}
        empty="No records in this range.">
        {r.data?.rows.map((row, i) => (
          <tr key={i}>
            {row.map((c, j) => <td key={j} className={typeof c === 'number' ? 'tabular-nums' : ''}>{c === '' ? '—' : c.toLocaleString()}</td>)}
          </tr>
        ))}
      </Table>
      {r.data && r.data.total_rows > r.data.rows.length && (
        <p className="text-xs text-muted">Showing the first {r.data.rows.length} of {r.data.total_rows} rows. The PDF and CSV have all of them.</p>
      )}
    </>
  );
}
