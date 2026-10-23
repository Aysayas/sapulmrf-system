import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useMyAdjustments, useRequestAdjustment } from '../../api/approvals';
import { useItems } from '../../api/masterdata';
import { useInventory, type InventoryView } from '../../api/operations';
import { FillBar } from '../../components/charts';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';

type StockRow = InventoryView['stock'][number];

export default function StoragePage() {
  const inv = useInventory();
  const mine = useMyAdjustments();
  const [adjusting, setAdjusting] = useState<StockRow | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Storage" sub="What is stored where, and how full each area is." />
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
      <Toast message={done} />
    </>
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
