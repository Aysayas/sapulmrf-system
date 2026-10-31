import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useIntake, useRecordSegregation, useUndoSegregation, useWaiting, type Delivery } from '../../api/operations';
import { Badge, btn, Drawer, inputCls, PageHeader } from '../../components/ui';
import { when } from '../operations/shared';
import { Card, Field, touch } from './shared';

// Two decimals here: the difference from received is often under 1 kg.
const kg2 = (n: number) => `${n.toFixed(2)} kg`;
const CONDITION = { segregated: 'Properly segregated', mixed: 'Mixed' } as const;
const isToday = (iso: string) => new Date(iso).toDateString() === new Date().toDateString();

export default function SegregationPage() {
  const waiting = useWaiting('segregation');
  // shortcut: only sees deliveries received in the last 7 days (max 100), widen if older ones get checked often.
  const recent = useIntake(7);
  const checked = recent.data?.filter((d) => d.segregation && isToday(d.segregation.checked_at));
  const [recording, setRecording] = useState<Delivery | null>(null);
  const [done, setDone] = useState<{ id: number; message: string } | null>(null);
  const undo = useUndoSegregation();

  return (
    <>
      <PageHeader title="Segregation check" sub="Record if each delivery was segregated, then weigh the wet and dry parts." />

      <h2 className="text-lg font-bold">Awaiting separation</h2>
      <ul aria-label="Awaiting separation" className="flex flex-col gap-2">
        {waiting.isPending && <li className="text-muted">Loading…</li>}
        {waiting.error && <li role="alert" className="text-crit">{waiting.error.message}</li>}
        {waiting.data?.length === 0 && <li className="text-muted">Nothing is waiting for a check.</li>}
        {waiting.data?.map((d) => (
          <Card key={d.id} label={d.code}>
            <div className="flex items-start gap-2">
              <b className="flex-1">{d.code} · {d.source_area}</b>
              <Badge kind="warn">Awaiting</Badge>
            </div>
            <p className="text-sm text-ink-2">Received <b>{kg2(d.weight_kg)}</b> · {when(d.received_at)}</p>
            <button className={`${btn.base} ${btn.primary} ${touch} mt-2 w-full`} onClick={() => setRecording(d)}>Record</button>
          </Card>
        ))}
      </ul>

      <h2 className="text-lg font-bold">Checked today</h2>
      <ul aria-label="Checked today" className="flex flex-col gap-2">
        {recent.isPending && <li className="text-muted">Loading…</li>}
        {recent.error && <li role="alert" className="text-crit">{recent.error.message}</li>}
        {checked?.length === 0 && <li className="text-muted">No checks yet today.</li>}
        {checked?.map((d) => (
          <Card key={d.id} label={d.code}>
            <div className="flex items-start gap-2">
              <b className="flex-1">{d.code} · {d.source_area}</b>
              <Badge kind={d.segregation!.condition === 'segregated' ? 'ok' : 'neutral'}>{d.segregation!.condition === 'segregated' ? 'Segregated' : 'Mixed'}</Badge>
            </div>
            <p className="text-sm text-ink-2">Wet {kg2(d.segregation!.wet_kg)} · Dry {kg2(d.segregation!.dry_kg)}</p>
          </Card>
        ))}
      </ul>

      {recording && <RecordSheet d={recording} onClose={() => setRecording(null)} onSaved={(message) => { setDone({ id: recording.id, message }); setRecording(null); undo.reset(); }} />}
      {undo.error && <p role="alert" className="text-sm text-crit">{undo.error.message}</p>}
      {/* Stays until dismissed, not the usual timed toast: the Undo must still be there when the mistake is noticed. */}
      {done && (
        <div role="status" className="fixed inset-x-4 bottom-20 z-30 rounded-lg bg-leaf-900 px-4 py-3 text-sm text-white shadow-xl">
          ✓ {done.message}
          <span className="mt-2 flex gap-2">
            <button className={`${btn.base} ${btn.secondary} ${btn.small}`} disabled={undo.isPending}
              onClick={() => undo.mutate(done.id, { onSuccess: () => setDone(null), onError: () => setDone(null) })}>Undo</button>
            <button className={`${btn.base} ${btn.secondary} ${btn.small}`} onClick={() => setDone(null)}>Dismiss</button>
          </span>
        </div>
      )}
    </>
  );
}

// Mirrors SegregationIn on the server, which also rejects wet + dry well above the received weight.
const part = (what: string) => z.number({ error: `Enter the ${what} kg, or 0.` }).min(0, 'Can’t be below 0.').max(5000, 'That is too much for one delivery.');
const schema = z.object({
  condition: z.enum(['segregated', 'mixed'], { error: 'How did it arrive?' }),
  wet_kg: part('wet'),
  dry_kg: part('dry'),
  note: z.string().trim().max(200, 'Keep the note under 200 characters.'),
});
type Form = z.infer<typeof schema>;

function RecordSheet({ d, onClose, onSaved }: { d: Delivery; onClose: () => void; onSaved: (m: string) => void }) {
  const send = useRecordSegregation();
  const { register, handleSubmit, formState, watch } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { note: '' } });
  const [wet, dry] = watch(['wet_kg', 'dry_kg']);
  const e = formState.errors;
  const total = wet + dry;
  const entered = Number.isFinite(total);

  const onSubmit = (f: Form) =>
    send.mutate({ deliveryId: d.id, ...f }, {
      onSuccess: () => onSaved(`${d.code} saved: ${f.condition === 'mixed' ? 'Mixed' : 'Segregated'} · wet ${kg2(f.wet_kg)} → compost · dry ${kg2(f.dry_kg)} → sorting`),
    });

  return (
    <Drawer title={`Segregation check · ${d.code}`} onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending} onClick={handleSubmit(onSubmit)}>Save check</button>
      </>
    }>
      {send.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{send.error.message}</p>}
      <div className="rounded-lg bg-surface p-3 text-sm">
        <div className="text-xs text-muted">Source area</div>
        <b>{d.source_area}</b>
        <div className="mt-2 text-xs text-muted">Received</div>
        <b>{kg2(d.weight_kg)}</b> · {when(d.received_at)}
      </div>
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-semibold">How did it arrive?</legend>
        {(['segregated', 'mixed'] as const).map((c) => (
          <label key={c} className={`${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`}>
            <input type="radio" value={c} className="accent-leaf-700" {...register('condition')} /> {CONDITION[c]}
          </label>
        ))}
        {e.condition && <span className="text-xs text-crit">{e.condition.message}</span>}
      </fieldset>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Wet waste (kg)" error={e.wet_kg?.message}>
          <input type="number" step="0.01" inputMode="decimal" className={`${inputCls} ${touch}`} aria-invalid={!!e.wet_kg} {...register('wet_kg', { valueAsNumber: true })} />
        </Field>
        <Field label="Dry waste (kg)" error={e.dry_kg?.message}>
          <input type="number" step="0.01" inputMode="decimal" className={`${inputCls} ${touch}`} aria-invalid={!!e.dry_kg} {...register('dry_kg', { valueAsNumber: true })} />
        </Field>
      </div>
      {entered && (
        <p className="rounded-lg bg-surface p-3 text-sm" aria-live="polite">
          Wet {wet.toFixed(2)} + dry {dry.toFixed(2)} = <b>{kg2(total)}</b>. Difference from received: <b>{kg2(Math.abs(d.weight_kg - total))}</b>.
        </p>
      )}
      <Field label="Note (optional)" error={e.note?.message}>
        <input className={`${inputCls} ${touch}`} aria-invalid={!!e.note} placeholder="e.g. Food scraps mixed with plastic" {...register('note')} />
      </Field>
    </Drawer>
  );
}
