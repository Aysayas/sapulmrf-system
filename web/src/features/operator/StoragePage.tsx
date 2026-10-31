import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useMyAdjustments, useRequestAdjustment } from '../../api/approvals';
import { useItems } from '../../api/masterdata';
import { useInventory, useTransfer, type InventoryView } from '../../api/operations';
import { FillBar } from '../../components/charts';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';

type StockRow = InventoryView['stock'][number];

export default function StoragePage() {
  const inv = useInventory();
  const mine = useMyAdjustments();
  const [adjusting, setAdjusting] = useState<StockRow | null>(null);
  const [transferring, setTransferring] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Storage" sub="What is stored where, and how full each area is." />
      <button className={`${btn.base} ${btn.primary} ${touch} w-full`} disabled={!inv.data?.stock.length} onClick={() => setTransferring(true)}>Transfer between areas</button>
      {inv.isPending && <p className="text-muted">Loading…</p>}
      {inv.error && <p className="text-crit">{inv.error.message}</p>}
      {inv.data && (
        <section aria-label="Storage areas" className="rounded-xl border border-line bg-white px-3 py-2">
          {inv.data.areas.map((a) => <FillBar key={a.id} area={a} />)}
        </section>
      )}

      <h2 className="text-lg font-bold">Stock</h2>
      <p className="-mt-3 text-sm text-ink-2">Counted something different? Tap the row to ask for an adjustment.</p>
      <ul aria-label="Stock" className="flex flex-col gap-2">
        {inv.data?.stock.length === 0 && <li className="text-muted">Nothing in storage.</li>}
        {inv.data?.stock.map((s) => (
          <li key={`${s.area}-${s.material}`}>
            <button className={`${touch} flex w-full items-center gap-3 rounded-xl border border-line bg-white p-3 text-left`}
              aria-label={`Request adjustment for ${s.material} in ${s.area}`} onClick={() => setAdjusting(s)}>
              <span className="flex-1">
                <b>{s.material}</b>
                <small className="block text-ink-2">{s.area} · {s.bags} bags</small>
              </span>
              <span className="font-bold tabular-nums">{kg(s.kg)}</span>
              <span aria-hidden className="text-muted">›</span>
            </button>
          </li>
        ))}
      </ul>

      <h2 className="text-lg font-bold">My requests</h2>
      <ul aria-label="My requests" className="flex flex-col gap-2">
        {mine.isPending && <li className="text-muted">Loading…</li>}
        {mine.error && <li className="text-crit">{mine.error.message}</li>}
        {mine.data?.length === 0 && <li className="text-muted">No adjustment requests in the last 30 days.</li>}
        {mine.data?.map((r) => (
          <Card key={r.id} label={`${r.material} in ${r.area}`}>
            <div className="flex items-start gap-2">
              <b className="flex-1">{r.material} · {r.area}</b>
              <StatusBadge status={r.status} />
            </div>
            <p className="text-sm text-ink-2">{kg(r.system_kg)} → {kg(r.actual_kg)} · {r.reason}</p>
            <p className="text-xs text-muted">Sent {when(r.requested_at)}{r.decided_by ? ` · ${r.status} by ${r.decided_by}` : ''}</p>
            {r.comment && <p className="mt-1 text-sm">“{r.comment}”</p>}
          </Card>
        ))}
      </ul>

      {adjusting && (
        <AdjustSheet row={adjusting} onClose={() => setAdjusting(null)}
          onSent={(m) => { setAdjusting(null); setDone(m); }} />
      )}
      {transferring && inv.data && (
        <TransferSheet view={inv.data} onClose={() => setTransferring(false)}
          onSent={(m) => { setTransferring(false); setDone(m); }} />
      )}
      <Toast message={done} />
    </>
  );
}

// Mirrors TransferIn on the server, which stays the authority on what fits.
const transferSchema = z.object({
  material: z.string().min(1, 'Pick the material.'),
  from_area_id: z.number().positive('Pick where it comes from.'),
  to_area_id: z.number().positive('Pick where it goes.'),
  bags: z.number({ error: 'Enter the bags, or 0.' }).int('Whole bags only.').min(0, 'Can’t be below 0.').max(1000),
  kg: z.number({ error: 'Enter the kg.' }).min(0.01, 'Enter the kg.').max(50000),
});
type TransferForm = z.infer<typeof transferSchema>;

function TransferSheet({ view, onClose, onSent }: { view: InventoryView; onClose: () => void; onSent: (m: string) => void }) {
  const materials = useItems('materials');
  const send = useTransfer();
  const { register, handleSubmit, setValue, formState: { errors: e }, watch } = useForm<TransferForm>({
    resolver: zodResolver(transferSchema),
    defaultValues: { material: '', from_area_id: 0, to_area_id: 0, bags: 0 },
  });
  const [material, fromId, toId, weight] = watch(['material', 'from_area_id', 'to_area_id', 'kg']);
  const from = view.areas.find((a) => a.id === fromId);
  const to = view.areas.find((a) => a.id === toId);
  const materialId = material === 'Residual' ? null : materials.data?.find((m) => m.name === material)?.id;
  const moving = weight > 0 ? weight : 0;
  const pctOf = (a: typeof view.areas[number], change: number) => Math.round((a.kg + change) / a.capacity_kg * 100);

  const onSubmit = (f: TransferForm) =>
    send.mutate({ material_id: materialId!, from_area_id: f.from_area_id, to_area_id: f.to_area_id, kg: f.kg, bags: f.bags },
      { onSuccess: (t) => onSent(`Moved ${kg(t.kg)} ${t.material} · ${t.from_area} to ${t.to_area}`) });

  return (
    <Drawer title="Transfer between areas" onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={materialId === undefined && !!material || send.isPending} onClick={handleSubmit(onSubmit)}>
          {moving ? `Transfer ${kg(moving)}` : 'Transfer'}
        </button>
      </>
    }>
      {(send.error ?? materials.error) && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{(send.error ?? materials.error)!.message}</p>}
      <Field label="Material" error={e.material?.message}>
        <select className={`${inputCls} ${touch}`} aria-invalid={!!e.material}
          {...register('material', { onChange: () => setValue('from_area_id', 0) })}>
          <option value="">Pick a material</option>
          {[...new Set(view.stock.map((s) => s.material))].map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </Field>
      <Field label="From" error={e.from_area_id?.message}>
        <select className={`${inputCls} ${touch}`} aria-invalid={!!e.from_area_id}
          {...register('from_area_id', { valueAsNumber: true, onChange: () => setValue('to_area_id', 0) })}>
          <option value={0}>{material ? 'Pick an area' : 'Pick the material first'}</option>
          {view.stock.filter((s) => s.material === material).map((s) => (
            <option key={s.area} value={view.areas.find((a) => a.name === s.area)?.id ?? 0}>{s.area} · {kg(s.kg)} · {s.bags} bags</option>
          ))}
        </select>
      </Field>
      <Field label="To" error={e.to_area_id?.message}>
        <select className={`${inputCls} ${touch}`} aria-invalid={!!e.to_area_id} {...register('to_area_id', { valueAsNumber: true })}>
          <option value={0}>Pick an area</option>
          {view.areas.filter((a) => a.id !== fromId).map((a) => (
            <option key={a.id} value={a.id}>{a.name} · {Math.round(a.kg)}/{a.capacity_kg} kg</option>
          ))}
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Bags" error={e.bags?.message}>
          <input type="number" step="1" min="0" inputMode="numeric" className={`${inputCls} ${touch}`} aria-invalid={!!e.bags} {...register('bags', { valueAsNumber: true })} />
        </Field>
        <Field label="kg" error={e.kg?.message}>
          <input type="number" step="0.1" min="0" inputMode="decimal" className={`${inputCls} ${touch}`} aria-invalid={!!e.kg} {...register('kg', { valueAsNumber: true })} />
        </Field>
      </div>
      {from && to && (
        <p className="rounded-lg bg-surface p-3 text-sm" aria-live="polite">
          After transfer: <b>{from.name} {pctOf(from, -moving)}%</b> · <b className={pctOf(to, moving) > 100 ? 'text-crit' : ''}>{to.name} {pctOf(to, moving)}%</b>
        </p>
      )}
      <p className="text-sm text-ink-2">Moving all of a material takes all its bags.</p>
    </Drawer>
  );
}

const schema = z.object({
  actual_kg: z.number({ error: 'Enter the kg you counted.' }).min(0, 'Can’t be below 0.').max(50000, 'That is more than any area holds.'),
  reason: z.string().trim().min(1, 'Say why the count is different.').max(120),
  details: z.string().trim().max(200),
});
type Form = z.infer<typeof schema>;

function AdjustSheet({ row, onClose, onSent }: { row: StockRow; onClose: () => void; onSent: (m: string) => void }) {
  const materials = useItems('materials');
  const areas = useItems('storage-areas');
  const send = useRequestAdjustment();
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { reason: '', details: '' } });
  const areaId = areas.data?.find((a) => a.name === row.area)?.id;
  const materialId = row.material === 'Residual' ? null : materials.data?.find((m) => m.name === row.material)?.id;
  const ready = areaId !== undefined && materialId !== undefined;

  const onSubmit = (f: Form) =>
    send.mutate({ material_id: materialId!, storage_area_id: areaId!, ...f },
      { onSuccess: () => onSent(`Adjustment sent for approval · ${row.material}, ${row.area}`) });

  return (
    <Drawer title="Request inventory adjustment" onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={!ready || send.isPending} onClick={handleSubmit(onSubmit)}>Send for approval</button>
      </>
    }>
      {send.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{send.error.message}</p>}
      <div className="rounded-lg bg-surface p-3 text-sm">
        <div className="text-xs text-muted">Material and area</div>
        <b>{row.material} · {row.area}</b>
        <div className="mt-2 text-xs text-muted">System says</div>
        <b>{kg(row.kg)}</b>
      </div>
      <Field label="Actual count (kg)" error={formState.errors.actual_kg?.message}>
        <input type="number" step="0.1" inputMode="decimal" className={inputCls} aria-invalid={!!formState.errors.actual_kg}
          {...register('actual_kg', { valueAsNumber: true })} />
      </Field>
      <Field label="Reason" error={formState.errors.reason?.message}>
        <input className={inputCls} placeholder="e.g. Wet paper removed as residual" aria-invalid={!!formState.errors.reason} {...register('reason')} />
      </Field>
      <Field label="Details (optional)" error={formState.errors.details?.message}>
        <textarea rows={3} className={inputCls} {...register('details')} />
      </Field>
      <p className="text-sm text-ink-2">Stock changes only after the Barangay Administrator approves.</p>
    </Drawer>
  );
}
