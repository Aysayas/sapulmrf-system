import { useState } from 'react';
import { useCompost } from '../../api/operations';
import { ReadingChart } from '../../components/charts';
import { Badge, PageHeader } from '../../components/ui';
import { kg, Table, when } from './shared';

const ACTIVITY = { turning: 'Turned', watering: 'Watered', inspection: 'Inspected' } as Record<string, string>;

export default function CompostPage() {
  const [batch, setBatch] = useState<string>();
  const c = useCompost(batch);
  const r = c.data?.ranges;
  const sel = c.data?.batches.find((b) => b.code === c.data?.selected);
  return (
    <>
      <PageHeader title="Compost and sensors" sub="Active batches and finished ones from the last 30 days, with the compost sensor readings" />
      <Table label="Compost batches" head={['Batch', 'Started', 'Start weight', 'Sensor', 'Latest reading', 'Status', '']}
        state={{ isPending: c.isPending, error: c.error, count: c.data?.batches.length }} empty="No compost batches yet.">
        {c.data?.batches.map((b) => (
          <tr key={b.id} className={b.code === c.data?.selected ? 'bg-surface' : ''}>
            <td className="font-semibold">{b.code}</td>
            <td className="whitespace-nowrap text-ink-2">{when(b.started_at)} · day {b.day}</td>
            <td>{kg(b.start_kg)}</td>
            <td>{b.sensor ?? '—'}</td>
            <td className="whitespace-nowrap">{b.temp_c === null ? '—' : `${b.temp_c} °C · ${b.moisture_pct}% moisture`}</td>
            <td>
              {b.finished_at ? <Badge>Finished · {kg(b.produced_kg ?? 0)} compost</Badge>
                : b.in_range === false ? <Badge kind="crit">Out of range</Badge>
                : b.in_range ? <Badge kind="ok">In range</Badge> : <Badge kind="dash">No reading</Badge>}
            </td>
            <td>
              <button className="text-xs font-semibold text-leaf-700 underline" aria-pressed={b.code === c.data?.selected} onClick={() => setBatch(b.code)}>
                Show readings
              </button>
            </td>
          </tr>
        ))}
      </Table>
      {sel && r && (
        <>
          <h3 className="text-sm font-bold">{sel.code}: last 24 hours of readings</h3>
          {c.data!.series.length === 0 ? <p className="text-sm text-ink-2">No readings in the last 24 hours.</p> : (
            <div className="grid grid-cols-2 gap-4">
              <section aria-label="Temperature" className="rounded-xl border border-line bg-white p-4">
                <h4 className="mb-2 text-sm font-bold">Temperature (°C)</h4>
                <ReadingChart data={c.data!.series} field="temp_c" unit="°C" min={r.compost_temp_min} max={r.compost_temp_max} />
              </section>
              <section aria-label="Moisture" className="rounded-xl border border-line bg-white p-4">
                <h4 className="mb-2 text-sm font-bold">Moisture (%)</h4>
                <ReadingChart data={c.data!.series} field="moisture_pct" unit="%" min={r.moisture_min} max={r.moisture_max} />
              </section>
            </div>
          )}
          <Table label="Batch activities" head={['When', 'Activity', 'By', 'Note']} state={{ isPending: false, error: null, count: sel.activities.length }}
            empty="No activities logged for this batch.">
            {sel.activities.slice(0, 20).map((a, i) => (
              <tr key={i}>
                <td className="whitespace-nowrap text-ink-2">{when(a.at)}</td>
                <td className="font-semibold">{ACTIVITY[a.type] ?? a.type}</td>
                <td>{a.by ?? '—'}</td>
                <td className="text-ink-2">{a.note || '—'}</td>
              </tr>
            ))}
          </Table>
        </>
      )}
    </>
  );
}
