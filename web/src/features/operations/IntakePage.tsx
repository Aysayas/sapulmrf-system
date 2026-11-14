import { useState } from 'react';
import { useUndo } from '../../api/approvals';
import { useIntake, type Delivery } from '../../api/operations';
import { Badge, btn, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, Period, Table, when } from './shared';

const PERIODS = [['Today', 1], ['This week', 7], ['This month', 31], ['All', undefined]] as const;
const STATUS = { awaiting: ['warn', 'Awaiting segregation'], separated: ['neutral', 'Separated'], sorted: ['ok', 'Sorted'] } as const;

export default function IntakePage() {
  const [days, setDays] = useState<number | undefined>(7);
  const [q, setQ] = useState('');
  const list = useIntake(days, q.trim());
  const [done, setDone] = useState<string | null>(null);
  return (
    <>
      <PageHeader title="Intake records" sub="Household waste deliveries weighed at the MRF, newest first (up to 100)" />
      <div className="flex items-center gap-3">
        <Period value={days} options={PERIODS} onChange={setDays} />
        <input type="search" aria-label="Search deliveries" placeholder="Search code, source area or category" className={`${inputCls} ml-auto w-80`}
          value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Table label="Deliveries" head={['Code', 'Received', 'Source area', 'Category', 'Weight', 'Segregation', 'Status', 'Recorded by', '']}
        state={{ isPending: list.isPending, error: list.error, count: list.data?.length }} empty="No deliveries for this filter.">
        {list.data?.map((d) => (
          <tr key={d.id}>
            <td className="font-semibold whitespace-nowrap">{d.code}</td>
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
            <td><UndoCell d={d} onDone={setDone} /></td>
          </tr>
        ))}
      </Table>
      <Toast message={done} />
    </>
  );
}

const STEPS = {
  sorted: [['sort', 'The sort'], ['segregation', 'Wet/dry and sort'], ['delivery', 'The whole record']],
  separated: [['segregation', 'The wet/dry check'], ['delivery', 'The whole record']],
  awaiting: [['delivery', 'The whole record']],
} as const;

/** Undo a delivery's newest steps with a reason; an operator records it again. Shows as a fix to review. */
function UndoCell({ d, onDone }: { d: Delivery; onDone: (m: string) => void }) {
  const undo = useUndo();
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState<'sort' | 'segregation' | 'delivery'>(STEPS[d.status][0][0]);
  const [why, setWhy] = useState('');
  if (!open) return <button className={`${btn.base} ${btn.small} ${btn.secondary}`} aria-label={`Undo ${d.code}`} onClick={() => { setTo(STEPS[d.status][0][0]); setOpen(true); }}>Undo…</button>;  // the stage may have changed
  return (
    <span className="flex items-center gap-1.5">
      <select aria-label={`What to undo on ${d.code}`} className={`${inputCls} w-44`} value={to} onChange={(e) => setTo(e.target.value as typeof to)}>
        {STEPS[d.status].map(([v, label]) => <option key={v} value={v}>{label}</option>)}
      </select>
      <input aria-label={`Why undo ${d.code}`} className={`${inputCls} w-40`} placeholder="Why?" value={why} maxLength={120} onChange={(e) => setWhy(e.target.value)} />
      <button className={`${btn.base} ${btn.small} ${btn.primary}`} disabled={!why.trim() || undo.isPending}
        onClick={() => undo.mutate({ delivery_id: d.id, to, reason: why.trim() }, { onSuccess: () => { setOpen(false); onDone(`${d.code}: undone. An operator records it again.`); } })}>Undo</button>
      <button className={`${btn.base} ${btn.small} ${btn.secondary}`} onClick={() => setOpen(false)}>Cancel</button>
      {undo.error && <span role="alert" className="text-xs font-semibold text-crit">{undo.error.message}</span>}
    </span>
  );
}
