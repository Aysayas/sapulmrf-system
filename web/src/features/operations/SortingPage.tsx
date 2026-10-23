import { useState } from 'react';
import { useSorting } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { Badge, PageHeader } from '../../components/ui';
import { kg, Period, Table, when } from './shared';

const PERIODS = [['Today', 1], ['This week', 7], ['This month', 31]] as const;

export default function SortingPage() {
  const [days, setDays] = useState(1);
  const s = useSorting(days);
  const state = (count?: number) => ({ isPending: s.isPending, error: s.error, count });
  return (
    <>
      <PageHeader title="Sorting and camera records" sub="What the sorting camera suggested, what the operator confirmed, and the bags sorted into storage" />
      <Period value={days} options={PERIODS} onChange={setDays} />
      {s.data && (
        <div className="grid grid-cols-5 gap-4">
          <Kpi label="Items classified" value={String(s.data.classified)} />
          <Kpi label="Camera accepted" value={`${s.data.accepted_pct}%`} sub={`${s.data.unchanged} kept as suggested`} />
          <Kpi label="Changed by operator" value={String(s.data.changed)} />
          <Kpi label="Waiting to confirm" value={String(s.data.pending)} />
          <Kpi label="Sorted into storage" value={kg(s.data.sorted_kg)} />
        </div>
      )}
      <h3 className="text-sm font-bold">Camera classifications</h3>
      <Table label="Camera classifications" head={['Time', 'Photo', 'Camera suggested', 'Final', 'Confirmed by', 'Reason']}
        state={state(s.data?.classifications.length)} empty="No camera results in this period.">
        {s.data?.classifications.map((c) => (
          <tr key={c.id}>
            <td className="whitespace-nowrap text-ink-2">{when(c.suggested_at)}</td>
            <td><img src={c.image_url} alt={`Item suggested as ${c.suggested}`} className="h-10 w-14 rounded object-cover" loading="lazy" /></td>
            <td className="whitespace-nowrap">{c.suggested} · {Math.round(c.confidence * 100)}%</td>
            <td className="whitespace-nowrap">
              {c.final === null ? <Badge kind="dash">Waiting</Badge> : c.changed ? <Badge kind="warn">Changed to {c.final}</Badge> : <Badge kind="ok">{c.final}</Badge>}
            </td>
            <td className="text-ink-2">{c.confirmed_by ?? '—'}</td>
            <td className="text-ink-2">{c.reason || '—'}</td>
          </tr>
        ))}
      </Table>
      <h3 className="text-sm font-bold">Sorted into storage</h3>
      <Table label="Sorted bags" head={['Time', 'Delivery', 'Material', 'Bags', 'Weight', 'Storage area']}
        state={state(s.data?.sorted.length)} empty="Nothing sorted in this period.">
        {s.data?.sorted.map((r, i) => (
          <tr key={i}>
            <td className="whitespace-nowrap text-ink-2">{when(r.at)}</td>
            <td className="font-semibold">{r.delivery ?? '—'}</td>
            <td>{r.material}</td>
            <td>{r.bags}</td>
            <td>{kg(r.kg)}</td>
            <td>{r.area}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}
