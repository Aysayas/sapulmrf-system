import { useState } from 'react';
import { useIntake } from '../../api/operations';
import { Badge, inputCls, PageHeader } from '../../components/ui';
import { kg, Period, Table, when } from './shared';

const PERIODS = [['Today', 1], ['This week', 7], ['This month', 31], ['All', undefined]] as const;
const STATUS = { awaiting: ['warn', 'Awaiting segregation'], separated: ['neutral', 'Separated'], sorted: ['ok', 'Sorted'] } as const;

export default function IntakePage() {
  const [days, setDays] = useState<number | undefined>(7);
  const [q, setQ] = useState('');
  const list = useIntake(days, q.trim());
  return (
    <>
      <PageHeader title="Intake records" sub="Household waste deliveries weighed at the MRF, newest first (up to 100)" />
      <div className="flex items-center gap-3">
        <Period value={days} options={PERIODS} onChange={setDays} />
        <input type="search" aria-label="Search deliveries" placeholder="Search code, source area or category" className={`${inputCls} ml-auto w-80`}
          value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Table label="Deliveries" head={['Code', 'Received', 'Source area', 'Category', 'Weight', 'Segregation', 'Status', 'Recorded by']}
        state={{ isPending: list.isPending, error: list.error, count: list.data?.length }} empty="No deliveries for this filter.">
        {list.data?.map((d) => (
          <tr key={d.id}>
            <td className="font-semibold">{d.code}</td>
            <td className="whitespace-nowrap text-ink-2">{when(d.received_at)}</td>
            <td>{d.source_area}</td>
            <td>{d.category}</td>
            <td className="whitespace-nowrap">
              {kg(d.weight_kg)}{' '}
              {d.corrected && <span title={d.correction_reason ?? ''}><Badge kind="warn">Corrected from {kg(d.scale_kg ?? 0)}</Badge></span>}
              {d.weighed_by === 'manual' && !d.corrected && <Badge>Manual</Badge>}
            </td>
            <td className="whitespace-nowrap">
              {d.segregation
                ? `${d.segregation.condition === 'segregated' ? 'Segregated' : 'Mixed'} · wet ${kg(d.segregation.wet_kg)} · dry ${kg(d.segregation.dry_kg)}`
                : '—'}
            </td>
            <td><Badge kind={STATUS[d.status][0]}>{STATUS[d.status][1]}</Badge></td>
            <td className="text-ink-2">{d.recorded_by ?? '—'}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}
