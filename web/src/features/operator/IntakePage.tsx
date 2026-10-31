import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useItems } from '../../api/masterdata';
import { useIntake, useRecordDelivery, type Delivery } from '../../api/operations';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, Period, when } from '../operations/shared';
import { Card, Field, touch } from './shared';

const PERIODS = [['Today', 1], ['This week', 7], ['All', undefined]] as const;
const STATUS = { awaiting: ['warn', 'Awaiting separation'], separated: ['neutral', 'Separated'], sorted: ['ok', 'Sorted'] } as const;

/** One delivery in a phone list. Today uses it too. */
export function DeliveryCard({ d }: { d: Delivery }) {
  const weighed = d.corrected ? 'Scale · corrected' : d.weighed_by === 'manual' ? 'Manual' : 'Scale';
  return (
    <Card label={d.code}>
      <div className="flex items-start gap-2">
        <b className="flex-1">{d.code} · {d.source_area}</b>
        <Badge kind={STATUS[d.status][0]}>{STATUS[d.status][1]}</Badge>
      </div>
      <p className="text-sm text-ink-2">{d.category} · <b>{kg(d.weight_kg)}</b> · {weighed}</p>
      <p className="text-xs text-muted">{when(d.received_at)}</p>
    </Card>
  );
}

export default function IntakePage() {
  const [days, setDays] = useState<number | undefined>(1);
  const [q, setQ] = useState('');
  const list = useIntake(days, q.trim());
  const [adding, setAdding] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Waste intake" sub="Register each household delivery." />
      <button className={`${btn.base} ${btn.primary} ${touch} w-full`} onClick={() => setAdding(true)}>+ New delivery</button>
      <div className="[&_button]:min-h-11"><Period value={days} options={PERIODS} onChange={setDays} /></div>
      <input type="search" aria-label="Search deliveries" placeholder="Search delivery or purok" className={`${inputCls} ${touch}`}
        value={q} onChange={(e) => setQ(e.target.value)} />
      <ul aria-label="Deliveries" className="flex flex-col gap-2">
        {list.isPending && <li className="text-muted">Loading…</li>}
        {list.error && <li role="alert" className="text-crit">{list.error.message}</li>}
        {list.data?.length === 0 && <li className="text-muted">No deliveries for this filter.</li>}
        {list.data?.map((d) => <DeliveryCard key={d.id} d={d} />)}
      </ul>

      {adding && <NewDeliverySheet onClose={() => setAdding(false)} onSaved={(m) => { setAdding(false); setDone(m); }} />}
      <Toast message={done} />
    </>
  );
}

// Mirrors DeliveryIn on the server, which stays the authority.
const schema = z.object({
  source_area_id: z.number().min(1, 'Pick the source area.'),
  category_id: z.number().min(1, 'Pick the category.'),
  weight_kg: z.number({ error: 'Enter the weight.' }).gt(0, 'Enter the weight.').max(5000, 'That is more than one delivery can weigh.'),
});
type Form = z.infer<typeof schema>;

function NewDeliverySheet({ onClose, onSaved }: { onClose: () => void; onSaved: (m: string) => void }) {
  const puroks = useItems('puroks');
  const categories = useItems('categories');
  const send = useRecordDelivery();
  const { register, handleSubmit, formState, getValues } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { source_area_id: 0, category_id: 0 },
  });
  const [confirming, setConfirming] = useState(false);
  const e = formState.errors;
  const lists = puroks.error ?? categories.error;

  const name = (items: typeof puroks.data, id: number) => items?.find((i) => i.id === id)?.name;
  const v = getValues();
  const save = () =>
    send.mutate({ ...v, weighed_by: 'manual' }, { onSuccess: (d) => onSaved(`${d.code} saved · ${d.source_area} · ${kg(d.weight_kg)}`) });

  return (
    <Drawer title={confirming ? 'Confirm weight' : 'New delivery'} onClose={onClose} footer={
      confirming ? (
        <>
          <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={() => setConfirming(false)}>Back</button>
          <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending} onClick={save}>Confirm {v.weight_kg} kg</button>
        </>
      ) : (
        <>
          <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
          <button className={`${btn.base} ${btn.primary} ${touch}`} onClick={handleSubmit(() => setConfirming(true))}>Next</button>
        </>
      )
    }>
      <p className="text-sm text-muted">Step {confirming ? 2 : 1} of 2</p>
      {lists && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{lists.message}</p>}
      {send.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{send.error.message}</p>}
      {confirming ? (
        <div className="rounded-lg bg-surface p-3 text-sm">
          <div className="text-xs text-muted">Source area</div>
          <b>{name(puroks.data, v.source_area_id)}</b>
          <div className="mt-2 text-xs text-muted">Category</div>
          <b>{name(categories.data, v.category_id)}</b>
          <div className="mt-2 text-xs text-muted">Weight · typed in</div>
          <b className="block text-3xl font-extrabold">{v.weight_kg} kg</b>
        </div>
      ) : (
        <>
          <Field label="Source area" error={e.source_area_id?.message}>
            <select className={`${inputCls} ${touch}`} aria-invalid={!!e.source_area_id} {...register('source_area_id', { valueAsNumber: true })}>
              <option value={0}>{puroks.isPending ? 'Loading…' : 'Pick a source area'}</option>
              {puroks.data?.filter((p) => p.active).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </Field>
          <Field label="Category" error={e.category_id?.message}>
            <select className={`${inputCls} ${touch}`} aria-invalid={!!e.category_id} {...register('category_id', { valueAsNumber: true })}>
              <option value={0}>{categories.isPending ? 'Loading…' : 'Pick a category'}</option>
              {categories.data?.filter((c) => c.active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="Weight (kg)" error={e.weight_kg?.message}>
            <input type="number" step="0.01" inputMode="decimal" className={`${inputCls} ${touch}`} aria-invalid={!!e.weight_kg}
              {...register('weight_kg', { valueAsNumber: true })} />
          </Field>
          <p className="text-sm text-ink-2">The date and time are filled in automatically when you save.</p>
        </>
      )}
    </Drawer>
  );
}
