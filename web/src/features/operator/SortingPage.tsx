import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useItems, type Item } from '../../api/masterdata';
import { useConfirmClassification, usePendingClassifications, useSortDelivery, useSorting, useWaiting, type Classification, type Delivery } from '../../api/operations';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { when } from '../operations/shared';
import { Card, Field, touch } from './shared';

// shortcut: the API has no confidence threshold, so the cut-off lives here. Move it to the settings if admins need to tune it.
const LOW_CONFIDENCE = 0.6;
const kg2 = (n: number) => `${n.toFixed(2)} kg`;
const alertCls = 'rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit';

export default function SortingPage() {
  const pending = usePendingClassifications();
  const waiting = useWaiting('sorting');
  const today = useSorting(1);
  const confirm = useConfirmClassification();
  const [changing, setChanging] = useState<Classification | null>(null);
  const [recording, setRecording] = useState<number | 'pick' | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const t = today.data;

  return (
    <>
      <PageHeader title="Sorting" sub="Confirm or change what the camera suggests, then record the sorted quantities." />
      <button className={`${btn.base} ${btn.primary} ${touch} w-full`} onClick={() => setRecording('pick')}>Record sorted quantities</button>
      {t && (
        <p className="rounded-xl border border-line bg-white p-3 text-sm">
          Today: <b>{t.classified}</b> items · <b>{t.unchanged}</b> unchanged · <b>{t.changed}</b> changed · <b>{t.accepted_pct}%</b> accepted
        </p>
      )}

      <h2 className="text-lg font-bold">Camera suggestions</h2>
      {pending.error && <p className="text-crit">{pending.error.message}</p>}
      <ul aria-label="Camera suggestions" className="flex flex-col gap-2">
        {pending.isPending && <li className="text-muted">Loading…</li>}
        {pending.data?.length === 0 && <li className="text-muted">No suggestions waiting. New ones appear here by themselves.</li>}
        {pending.data?.map((c) => {
          const pct = Math.round(c.confidence * 100);
          const low = c.confidence < LOW_CONFIDENCE;
          const busy = confirm.isPending && confirm.variables?.id === c.id;
          return (
            <Card key={c.id} label={`Suggestion ${c.suggested}`}>
              <div className="flex items-start gap-3">
                {c.image_url && <img src={c.image_url} alt={`Item the camera read as ${c.suggested}`} className="size-16 rounded-lg object-cover" />}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start gap-2">
                    <b className="flex-1 text-lg">{c.suggested}{low && '?'}</b>
                    {low ? <Badge kind="warn">Not sure, check</Badge> : <Badge>Suggestion</Badge>}
                  </div>
                  <div className="flex justify-between text-xs text-ink-2"><span>Confidence</span><span>{pct}%</span></div>
                  <div className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                    <div className={`h-full ${low ? 'bg-warn' : 'bg-leaf-700'}`} style={{ width: `${pct}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-muted">{when(c.suggested_at)}</p>
                </div>
              </div>
              {confirm.error && confirm.variables?.id === c.id && <p role="alert" className={`mt-2 ${alertCls}`}>{confirm.error.message}</p>}
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={busy} onClick={() => confirm.mutate({ id: c.id })}>Confirm {c.suggested}</button>
                <button className={`${btn.base} ${btn.secondary} ${touch}`} disabled={busy} aria-label={`Change ${c.suggested}`} onClick={() => setChanging(c)}>Change</button>
              </div>
            </Card>
          );
        })}
      </ul>

      <h2 className="text-lg font-bold">Waiting for sorting</h2>
      {waiting.error && <p className="text-crit">{waiting.error.message}</p>}
      <ul aria-label="Waiting for sorting" className="flex flex-col gap-2">
        {waiting.isPending && <li className="text-muted">Loading…</li>}
        {waiting.data?.length === 0 && <li className="text-muted">No deliveries are waiting for sorting.</li>}
        {waiting.data?.map((d) => (
          <li key={d.id}>
            <button className={`${touch} flex w-full items-center gap-3 rounded-xl border border-line bg-white p-3 text-left`}
              aria-label={`Record sorted quantities for ${d.code}`} onClick={() => setRecording(d.id)}>
              <span className="flex-1">
                <b>{d.code}</b>
                <small className="block text-ink-2">{d.source_area} · {when(d.received_at)}</small>
              </span>
              <span className="font-bold tabular-nums">{kg2(d.segregation?.dry_kg ?? 0)} dry</span>
              <span aria-hidden className="text-muted">›</span>
            </button>
          </li>
        ))}
      </ul>

      {changing && <ChangeSheet item={changing} onClose={() => setChanging(null)} onSaved={(m) => { setChanging(null); setDone(m); }} />}
      {recording !== null && (
        <RecordSheet deliveryId={recording === 'pick' ? 0 : recording} onClose={() => setRecording(null)} onSaved={(m) => { setRecording(null); setDone(m); }} />
      )}
      <Toast message={done} />
    </>
  );
}

const changeSchema = z.object({
  choice: z.string({ error: 'Pick what it really is.' }).min(1, 'Pick what it really is.'),
  reason: z.string().trim().max(200),
});
type ChangeForm = z.infer<typeof changeSchema>;

function ChangeSheet({ item, onClose, onSaved }: { item: Classification; onClose: () => void; onSaved: (m: string) => void }) {
  const materials = useItems('materials');
  const send = useConfirmClassification();
  const { register, handleSubmit, formState } = useForm<ChangeForm>({ resolver: zodResolver(changeSchema), defaultValues: { reason: '' } });
  const options = materials.data?.filter((m) => m.active && m.name !== item.suggested) ?? [];

  const onSubmit = ({ choice, reason }: ChangeForm) =>
    send.mutate(
      choice === 'none' ? { id: item.id, not_recyclable: true, reason } : { id: item.id, final_material_id: Number(choice), reason },
      { onSuccess: (c) => onSaved(`Changed ${c.suggested} to ${c.final}`) },
    );

  return (
    <Drawer title={`Change ${item.suggested}`} onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending || !materials.data} onClick={handleSubmit(onSubmit)}>Save</button>
      </>
    }>
      {send.error && <p role="alert" className={alertCls}>{send.error.message}</p>}
      {materials.isPending && <p className="text-muted">Loading…</p>}
      {materials.error && <p className="text-crit">{materials.error.message}</p>}
      <p className="text-sm text-ink-2">The camera said {item.suggested} at {Math.round(item.confidence * 100)}%. What is it really?</p>
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-semibold">Material</legend>
        {options.map((m) => (
          <label key={m.id} className={`${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`}>
            <input type="radio" value={m.id} className="accent-leaf-700" {...register('choice')} /> {m.name}
          </label>
        ))}
        <label className={`${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`}>
          <input type="radio" value="none" className="accent-leaf-700" {...register('choice')} /> Not recyclable
        </label>
        {formState.errors.choice && <span className="text-xs text-crit">{formState.errors.choice.message}</span>}
      </fieldset>
      <Field label="Reason (optional)" error={formState.errors.reason?.message}>
        <input className={`${inputCls} ${touch}`} placeholder="e.g. Waxed carton, not paper" {...register('reason')} />
      </Field>
    </Drawer>
  );
}

// Mirrors SortIn on the server, which stays the authority (it also limits the total against the dry weight).
const recordSchema = z.object({
  delivery_id: z.number().min(1, 'Pick the delivery.'),
  rows: z.array(z.object({
    name: z.string(),
    material_id: z.number().nullable(),
    bags: z.number().or(z.nan()),
    kg: z.number().or(z.nan()),
    storage_area_id: z.number(),
  })),
}).superRefine((f, ctx) => {
  f.rows.forEach((r, i) => {
    if (r.kg < 0 || r.kg > 5000) ctx.addIssue({ code: 'custom', path: ['rows', i, 'kg'], message: 'Between 0 and 5,000 kg.' });
    if (r.bags < 0 || r.bags > 1000 || (r.bags && !Number.isInteger(r.bags))) ctx.addIssue({ code: 'custom', path: ['rows', i, 'bags'], message: 'Whole bags only.' });
    if (r.kg > 0 && !r.storage_area_id) ctx.addIssue({ code: 'custom', path: ['rows', i, 'storage_area_id'], message: 'Pick an area.' });
    if (r.bags > 0 && !(r.kg > 0)) ctx.addIssue({ code: 'custom', path: ['rows', i, 'kg'], message: 'Enter the kg.' });
  });
  if (!f.rows.some((r) => r.kg > 0)) ctx.addIssue({ code: 'custom', path: ['rows'], message: 'Enter the kg of at least one material.' });
});
type RecordForm = z.infer<typeof recordSchema>;

function RecordSheet({ deliveryId, onClose, onSaved }: { deliveryId: number; onClose: () => void; onSaved: (m: string) => void }) {
  const waiting = useWaiting('sorting');
  const materials = useItems('materials');
  const areas = useItems('storage-areas');
  const error = waiting.error ?? materials.error ?? areas.error;
  const ready = waiting.data && materials.data && areas.data;
  return ready ? (
    <RecordForm deliveries={waiting.data!} materials={materials.data!} areas={areas.data!} deliveryId={deliveryId} onClose={onClose} onSaved={onSaved} />
  ) : (
    <Drawer title="Record sorted quantities" onClose={onClose} footer={<button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>}>
      {error ? <p className="text-crit">{error.message}</p> : <p className="text-muted">Loading…</p>}
    </Drawer>
  );
}

// Mounted once the lists are in, so the form's rows are fixed for as long as it is open.
function RecordForm({ deliveries, materials, areas, deliveryId, onClose, onSaved }: {
  deliveries: Delivery[]; materials: Item[]; areas: Item[]; deliveryId: number; onClose: () => void; onSaved: (m: string) => void;
}) {
  const send = useSortDelivery();
  const { register, handleSubmit, formState, watch } = useForm<RecordForm>({
    resolver: zodResolver(recordSchema),
    defaultValues: {
      delivery_id: deliveryId,
      rows: [...materials.filter((m) => m.active).map((m) => ({ name: m.name, material_id: m.id })), { name: 'Residual', material_id: null }]
        .map((r) => ({ ...r, bags: NaN, kg: NaN, storage_area_id: 0 })),
    },
  });
  const e = formState.errors;
  const rows = watch('rows');
  const delivery = deliveries.find((d) => d.id === watch('delivery_id'));
  const dry = delivery?.segregation?.dry_kg ?? 0;
  const total = Math.round(rows.reduce((sum, r) => sum + (r.kg > 0 ? r.kg : 0), 0) * 100) / 100;
  const diff = Math.round((dry - total) * 100) / 100;

  const onSubmit = (f: RecordForm) =>
    send.mutate({
      delivery_id: f.delivery_id,
      // Blank rows are simply not sorted; only what was weighed goes to storage.
      rows: f.rows.filter((r) => r.kg > 0).map((r) => ({ material_id: r.material_id, bags: r.bags || 0, kg: r.kg, storage_area_id: r.storage_area_id })),
    }, { onSuccess: (d) => onSaved(`${d.code} sorted · ${kg2(total)} added to storage`) });

  return (
    <Drawer title="Record sorted quantities" onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending} onClick={handleSubmit(onSubmit)}>Save and add to storage</button>
      </>
    }>
      {send.error && <p role="alert" className={alertCls}>{send.error.message}</p>}
      <Field label="From delivery" error={e.delivery_id?.message}>
        <select className={`${inputCls} ${touch}`} aria-invalid={!!e.delivery_id} {...register('delivery_id', { valueAsNumber: true })}>
          <option value={0}>{deliveries.length ? 'Pick a delivery' : 'No deliveries waiting'}</option>
          {deliveries.map((d) => <option key={d.id} value={d.id}>{d.code} · {d.source_area} · dry {kg2(d.segregation?.dry_kg ?? 0)}</option>)}
        </select>
      </Field>
      {rows.map((r, i) => {
        const re = e.rows?.[i];
        return (
          <fieldset key={r.name} className="rounded-lg border border-line p-3">
            <legend className="px-1 text-sm font-semibold">{r.name}</legend>
            <div className="grid grid-cols-[1fr_1fr_1.5fr] gap-2">
              <Field label="Bags" error={re?.bags?.message}>
                <input type="number" step="1" min="0" inputMode="numeric" aria-label={`${r.name} bags`} aria-invalid={!!re?.bags} className={`${inputCls} ${touch}`}
                  {...register(`rows.${i}.bags`, { valueAsNumber: true })} />
              </Field>
              <Field label="kg" error={re?.kg?.message}>
                <input type="number" step="0.01" min="0" inputMode="decimal" aria-label={`${r.name} kg`} aria-invalid={!!re?.kg} className={`${inputCls} ${touch}`}
                  {...register(`rows.${i}.kg`, { valueAsNumber: true })} />
              </Field>
              <Field label="Area" error={re?.storage_area_id?.message}>
                <select aria-label={`${r.name} storage area`} aria-invalid={!!re?.storage_area_id} className={`${inputCls} ${touch}`}
                  {...register(`rows.${i}.storage_area_id`, { valueAsNumber: true })}>
                  <option value={0}>Pick</option>
                  {areas.filter((a) => a.active).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </Field>
            </div>
          </fieldset>
        );
      })}
      {e.rows?.root?.message && <p className="text-xs text-crit">{e.rows.root.message}</p>}
      <p className={`rounded-lg p-3 text-sm ${diff < 0 ? 'bg-warn-100' : 'bg-surface'}`} aria-live="polite">
        {delivery
          ? <>Sorted <b>{kg2(total)}</b> of {kg2(dry)} dry waste. Difference <b>{kg2(Math.abs(diff))}</b>{diff < 0 && ' over'}.</>
          : 'Pick a delivery to see the difference.'}
      </p>
    </Drawer>
  );
}
