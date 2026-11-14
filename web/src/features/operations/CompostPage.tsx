import { useState } from 'react';
import { useCompost } from '../../api/operations';
import { Badge, PageHeader } from '../../components/ui';
import { kg, Table, when } from './shared';

const ACTIVITY = { turning: 'Turned', watering: 'Watered', inspection: 'Inspected' } as Record<string, string>;

// Compost is logged by hand by the operators: there is no compost sensor.
export default function CompostPage() {
  const [batch, setBatch] = useState<string>();
  const c = useCompost(batch);
  const sel = c.data?.batches.find((b) => b.code === c.data?.selected);
  return (
    <>
      <PageHeader title="Compost" sub={`Active batches and finished ones from the last 30 days, as logged by the operators${c.data ? ` · ${kg(c.data.wet_waiting_kg)} wet waste waiting` : ''}`} />
      <Table label="Compost batches" head={['Batch', 'Started', 'Start weight', 'Last activity', 'Status', '']}
        state={{ isPending: c.isPending, error: c.error, count: c.data?.batches.length }} empty="No compost batches yet.">
        {c.data?.batches.map((b) => (
          <tr key={b.id} className={b.code === c.data?.selected ? 'bg-surface' : ''}>
            <td className="font-semibold">{b.code}</td>
            <td className="whitespace-nowrap text-ink-2">{when(b.started_at)} · day {b.day}</td>
            <td>{kg(b.start_kg)}</td>
            <td className="whitespace-nowrap">{b.activities[0] ? `${ACTIVITY[b.activities[0].type] ?? b.activities[0].type} · ${when(b.activities[0].at)}` : '—'}</td>
            <td>{b.finished_at ? <Badge>Finished · {kg(b.produced_kg ?? 0)} compost</Badge> : <Badge kind="ok">Active</Badge>}</td>
            <td>
              <button className="text-xs font-semibold text-leaf-700 underline" aria-pressed={b.code === c.data?.selected} onClick={() => setBatch(b.code)}>
                Show activities
              </button>
            </td>
          </tr>
        ))}
      </Table>
      {sel && (
        <>
          <h3 className="text-sm font-bold">{sel.code}: activities</h3>
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
