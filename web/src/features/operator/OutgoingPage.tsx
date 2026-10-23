import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { OUTGOING_TYPE, useRequestOutgoing } from '../../api/approvals';
import { useItems } from '../../api/masterdata';
import { useInventory, useOutgoing } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, peso, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';

export default function OutgoingPage() {
  const out = useOutgoing(30);
  const [adding, setAdding] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const v = out.data;

  return (
    <>
      <PageHeader title="Outgoing" sub="Recyclables sold, compost given out, and residual sent for disposal." />
      <button className={`${btn.base} ${btn.primary} ${touch} w-full`} onClick={() => setAdding(true)}>+ Record outgoing</button>
      {out.isPending && <p className="text-muted">Loading…</p>}
      {out.error && <p className="text-crit">{out.error.message}</p>}
      {v && (
        <div className="grid grid-cols-2 gap-2">
          <Kpi label="Sold this month" value={kg(v.sold_kg_month)} sub="Recyclables" />
          <Kpi label="Income this month" value={peso(v.income_month)} sub="Approved sales only" />
          <Kpi label="Compost given out" value={kg(v.compost_kg_month)} sub="This month" />
          <Kpi label="Residual disposed" value={kg(v.disposed_kg_month)} sub="This month" />
        </div>
      )}

      <h2 className="text-lg font-bold">Records, last 30 days</h2>
      <ul aria-label="Outgoing records" className="flex flex-col gap-2">
        {v?.records.length === 0 && <li className="text-muted">Nothing recorded yet.</li>}
        {v?.records.map((o) => (
          <Card key={o.id} label={o.code}>
            <div className="flex items-start gap-2">
              <b className="flex-1">{o.code} · {OUTGOING_TYPE[o.type]}</b>
              <StatusBadge status={o.status} />
            </div>
            <p className="text-sm text-ink-2">
              {o.material} · {kg(o.kg)} · {o.recipient}
              {o.total !== null && ` · ${peso(o.price_per_kg!)}/kg = ${peso(o.total)}`}
            </p>
            <p className="text-xs text-muted">{when(o.requested_at)}{o.requested_by ? ` · ${o.requested_by}` : ''}</p>
            {o.comment && <p className="mt-1 text-sm">“{o.comment}”</p>}
          </Card>
        ))}
      </ul>

      {adding && <NewOutgoingSheet onClose={() => setAdding(false)} onSent={(m) => { setAdding(false); setDone(m); }} />}
      <Toast message={done} />
    </>
  );
}

// Mirrors OutgoingIn on the server, which stays the authority.
const schema = z.object({
  type: z.enum(['sale', 'compost', 'disposal']),
  material_id: z.number(),
  storage_area_id: z.number(),
  kg: z.number({ error: 'Enter the kg.' }).gt(0, 'Enter the kg.').max(50000),
  recipient: z.string().trim().min(1, 'Who is it going to?').max(120),
  price_per_kg: z.number().or(z.nan()),
}).superRefine((f, ctx) => {
  if (f.type === 'sale' && !f.material_id) ctx.addIssue({ code: 'custom', path: ['material_id'], message: 'Pick the material.' });
  if (f.type !== 'compost' && !f.storage_area_id) ctx.addIssue({ code: 'custom', path: ['storage_area_id'], message: 'Pick the storage area it leaves from.' });
  if (f.type === 'sale' && !(f.price_per_kg > 0)) ctx.addIssue({ code: 'custom', path: ['price_per_kg'], message: 'Enter the price per kg.' });
});
type Form = z.infer<typeof schema>;

function NewOutgoingSheet({ onClose, onSent }: { onClose: () => void; onSent: (m: string) => void }) {
  const materials = useItems('materials');
  const areas = useItems('storage-areas');
  const inv = useInventory();
  const compostOnHand = useOutgoing(30).data?.compost_on_hand_kg;
  const send = useRequestOutgoing();
  const { register, handleSubmit, formState, watch } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { type: 'sale', material_id: 0, storage_area_id: 0, recipient: '' },
  });
  const [type, materialId, weight, price] = watch(['type', 'material_id', 'kg', 'price_per_kg']);
  const e = formState.errors;

  // The areas holding what is going out, with how much is there.
  const material = type === 'disposal' ? 'Residual' : materials.data?.find((m) => m.id === materialId)?.name;
  const sources = (inv.data?.stock ?? []).filter((s) => s.material === material)
    .map((s) => ({ id: areas.data?.find((a) => a.name === s.area)?.id ?? 0, label: `${s.area} · ${kg(s.kg)}` }));

  const onSubmit = (f: Form) =>
    send.mutate({
      type: f.type,
      material_id: f.type === 'sale' ? f.material_id : null,
      storage_area_id: f.type === 'compost' ? null : f.storage_area_id,
      kg: f.kg,
      recipient: f.recipient,
      price_per_kg: f.type === 'sale' ? f.price_per_kg : null,
    }, { onSuccess: (o) => onSent(`${o.code} sent for approval · ${kg(o.kg)} ${o.material}`) });

  return (
    <Drawer title="Record outgoing material" onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending} onClick={handleSubmit(onSubmit)}>Send for approval</button>
      </>
    }>
      {send.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{send.error.message}</p>}
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-semibold">Type</legend>
        {([['sale', 'Recyclable sale'], ['compost', 'Compost'], ['disposal', 'Residual for disposal']] as const).map(([v, label]) => (
          <label key={v} className={`${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`}>
            <input type="radio" value={v} className="accent-leaf-700" {...register('type')} /> {label}
          </label>
        ))}
      </fieldset>
      {type === 'sale' && (
        <Field label="Material" error={e.material_id?.message}>
          <select className={inputCls} aria-invalid={!!e.material_id} {...register('material_id', { valueAsNumber: true })}>
            <option value={0}>Pick a material</option>
            {materials.data?.filter((m) => m.active).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </Field>
      )}
      {type !== 'compost' ? (
        <Field label="From storage" error={e.storage_area_id?.message}>
          <select className={inputCls} aria-invalid={!!e.storage_area_id} {...register('storage_area_id', { valueAsNumber: true })}>
            <option value={0}>{material ? 'Pick an area' : 'Pick the material first'}</option>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </Field>
      ) : (
        <p className="rounded-lg bg-surface p-3 text-sm">Compost on hand: <b>{compostOnHand === undefined ? '…' : kg(compostOnHand)}</b></p>
      )}
      <Field label={type === 'sale' ? 'Buyer' : 'Recipient'} error={e.recipient?.message}>
        <input className={inputCls} aria-invalid={!!e.recipient} placeholder={type === 'disposal' ? 'e.g. City ENRO truck' : 'e.g. Buyer A Junkshop'} {...register('recipient')} />
      </Field>
      <Field label="kg" error={e.kg?.message}>
        <input type="number" step="0.1" inputMode="decimal" className={inputCls} aria-invalid={!!e.kg} {...register('kg', { valueAsNumber: true })} />
      </Field>
      {type === 'sale' && (
        <>
          <Field label="Price per kg (₱)" error={e.price_per_kg?.message}>
            <input type="number" step="0.01" inputMode="decimal" className={inputCls} aria-invalid={!!e.price_per_kg} {...register('price_per_kg', { valueAsNumber: true })} />
          </Field>
          <p className="rounded-lg bg-surface p-3 text-sm" aria-live="polite">
            Total: <b>{weight > 0 && price > 0 ? peso(Math.round(weight * price * 100) / 100) : '—'}</b> <span className="text-muted">(kg × price)</span>
          </p>
        </>
      )}
      <p className="text-sm text-ink-2">Stock leaves storage only after the administrator approves.</p>
    </Drawer>
  );
}
