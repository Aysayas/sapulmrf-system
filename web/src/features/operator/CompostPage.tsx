import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useCompost, useLogBatchActivity, useStartBatch, type BatchLive } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, when } from '../operations/shared';
import { Card, Field, touch } from './shared';

const alertCls = 'rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit';
const ACTIVITIES = [['turning', 'Turning'], ['watering', 'Watering'], ['inspection', 'Inspection']] as const;
const activityName = (type: string) => ACTIVITIES.find(([v]) => v === type)?.[1] ?? type;

// Compost is logged by hand: there is no compost sensor.
const BatchBadge = ({ b }: { b: BatchLive }) => b.finished_at ? <Badge kind="dash">Finished</Badge> : <Badge kind="ok">Active</Badge>;

export default function CompostPage() {
  const [open, setOpen] = useState<string | undefined>();
  const compost = useCompost(open);
  const [starting, setStarting] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const v = compost.data;
  const batch = open ? v?.batches.find((b) => b.code === open) : undefined;

  return (
    <>
      {compost.error && <p role="alert" className={alertCls}>{compost.error.message}</p>}
      {batch && v ? (
        <BatchDetail batch={batch} onBack={() => setOpen(undefined)} onDone={setDone} />
      ) : (
        <>
          <PageHeader title="Compost" sub="Batches you log by hand: start weight, turning and watering, finished compost." />
          {v && <p className="text-sm font-semibold">{kg(v.wet_waiting_kg)} wet waste waiting for compost</p>}
          <button className={`${btn.base} ${btn.primary} ${touch} w-full`} onClick={() => setStarting(true)}>+ New batch</button>
          {compost.isPending && <p className="text-muted">Loading…</p>}
          <ul aria-label="Compost batches" className="flex flex-col gap-2">
            {v?.batches.length === 0 && <li className="text-muted">No compost batches yet. Start one when wet waste goes in.</li>}
            {v?.batches.map((b) => (
              <li key={b.id}>
                <button className={`${touch} w-full rounded-xl border border-line bg-white p-3 text-left`} aria-label={`Open batch ${b.code}`} onClick={() => setOpen(b.code)}>
                  <span className="flex items-start gap-2">
                    <b className="flex-1">{b.code}</b>
                    <BatchBadge b={b} />
                    <span aria-hidden className="text-muted">›</span>
                  </span>
                  {b.finished_at ? (
                    <small className="block text-ink-2">{when(b.finished_at)} · {b.produced_kg === null ? 'Finished' : `${kg(b.produced_kg)} compost`}</small>
                  ) : (
                    <>
                      <small className="block text-ink-2">Day {b.day} · started {when(b.started_at)} · {kg(b.start_kg)} wet waste</small>
                      <small className="block text-muted">
                        {b.activities[0] ? `${activityName(b.activities[0].type)} · ${when(b.activities[0].at)}` : 'No activity yet'}
                      </small>
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {starting && <StartSheet waiting={v?.wet_waiting_kg ?? 0} onClose={() => setStarting(false)} onSaved={(m) => { setStarting(false); setDone(m); }} />}
      <Toast message={done} />
    </>
  );
}

function BatchDetail({ batch: b, onBack, onDone }: { batch: BatchLive; onBack: () => void; onDone: (m: string) => void }) {
  const [sheet, setSheet] = useState<'log' | 'finish' | null>(null);
  const close = () => setSheet(null);

  return (
    <>
      <button className={`${btn.base} ${btn.secondary} ${touch} self-start`} onClick={onBack}>‹ All batches</button>
      <PageHeader title={`Batch ${b.code}`} sub={b.finished_at
        ? `Finished ${when(b.finished_at)}`
        : `Day ${b.day} · started ${when(b.started_at)}`} />
      <div><BatchBadge b={b} /></div>
      {!b.finished_at && (
        <div className="grid grid-cols-2 gap-2">
          <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={() => setSheet('finish')}>Mark finished</button>
          <button className={`${btn.base} ${btn.primary} ${touch}`} onClick={() => setSheet('log')}>+ Log activity</button>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Kpi label="Started with" value={kg(b.start_kg)} sub="Wet waste" />
        {b.finished_at
          ? <Kpi label="Compost made" value={b.produced_kg === null ? '—' : kg(b.produced_kg)} />
          : <Kpi label="Age" value={`Day ${b.day}`} sub={b.activities[0] ? `Last: ${activityName(b.activities[0].type)}, ${when(b.activities[0].at)}` : 'No activity yet'} />}
      </div>

      <h2 className="text-lg font-bold">Activity log</h2>
      <ul aria-label="Activity log" className="flex flex-col gap-2">
        {b.activities.length === 0 && <li className="text-muted">Nothing logged yet.</li>}
        {b.activities.map((a, i) => (
          <Card key={i} label={`${activityName(a.type)}, ${when(a.at)}`}>
            <b>{activityName(a.type)}</b>
            <p className="text-xs text-muted">{when(a.at)}{a.by ? ` · ${a.by}` : ''}</p>
            {a.note && <p className="mt-1 text-sm">{a.note}</p>}
          </Card>
        ))}
      </ul>

      {sheet && <ActivitySheet batch={b} finishing={sheet === 'finish'} onClose={close} onSaved={(m) => { close(); onDone(m); }} />}
    </>
  );
}

const startSchema = z.object({
  start_kg: z.number({ error: 'Enter the kg of wet waste.' }).gt(0, 'Enter the kg of wet waste.').max(5000, 'At most 5,000 kg.'),
});
type StartForm = z.infer<typeof startSchema>;

function StartSheet({ waiting, onClose, onSaved }: { waiting: number; onClose: () => void; onSaved: (m: string) => void }) {
  const send = useStartBatch();
  const { register, handleSubmit, formState } = useForm<StartForm>({ resolver: zodResolver(startSchema), defaultValues: { start_kg: waiting || undefined } });
  const e = formState.errors.start_kg;

  return (
    <Drawer title="Start compost batch" onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending}
          onClick={handleSubmit((f) => send.mutate({ start_kg: f.start_kg, sensor_id: null }, { onSuccess: (b) => onSaved(`${b.code} started · ${kg(b.start_kg)} wet waste`) }))}>Start batch</button>
      </>
    }>
      {send.error && <p role="alert" className={alertCls}>{send.error.message}</p>}
      <Field label="Wet waste (kg)" error={e?.message}>
        <input type="number" step="0.1" inputMode="decimal" className={`${inputCls} ${touch}`} aria-invalid={!!e} {...register('start_kg', { valueAsNumber: true })} />
      </Field>
      <p className="text-sm text-ink-2">Up to {kg(waiting)} waiting</p>
    </Drawer>
  );
}

// Mirrors ActivityIn on the server, which stays the authority. The server stamps the time.
const activitySchema = z.object({
  type: z.enum(['turning', 'watering', 'inspection']),
  note: z.string().trim().max(200, 'At most 200 characters.'),
  finished_kg: z.number().or(z.nan()),
});
type ActivityForm = z.infer<typeof activitySchema>;

function ActivitySheet({ batch, finishing, onClose, onSaved }: { batch: BatchLive; finishing: boolean; onClose: () => void; onSaved: (m: string) => void }) {
  const send = useLogBatchActivity();
  const { register, handleSubmit, formState, setError } = useForm<ActivityForm>({
    resolver: zodResolver(activitySchema),
    // Finishing is stored as a last inspection, the only activity that fits it.
    defaultValues: { type: finishing ? 'inspection' : 'turning', note: '', finished_kg: NaN },
  });
  const e = formState.errors;

  const onSubmit = ({ finished_kg, ...f }: ActivityForm) => {
    if (finishing && !(finished_kg > 0 && finished_kg <= 5000)) {
      setError('finished_kg', { message: 'Enter the kg of compost made, up to 5,000.' });
      return;
    }
    send.mutate({ batchId: batch.id, ...f, ...(finishing && { finished_kg }) }, {
      onSuccess: () => onSaved(finishing ? `${batch.code} finished · ${kg(finished_kg)} compost` : `${activityName(f.type)} logged on ${batch.code}`),
    });
  };

  return (
    <Drawer title={`${finishing ? 'Finish' : 'Log activity'} · ${batch.code}`} onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending} onClick={handleSubmit(onSubmit)}>{finishing ? 'Mark finished' : 'Save'}</button>
      </>
    }>
      {send.error && <p role="alert" className={alertCls}>{send.error.message}</p>}
      {finishing ? (
        <>
          <Field label="Compost made (kg)" error={e.finished_kg?.message}>
            <input type="number" step="0.1" inputMode="decimal" className={`${inputCls} ${touch}`} aria-invalid={!!e.finished_kg} {...register('finished_kg', { valueAsNumber: true })} />
          </Field>
          <p className="text-sm text-ink-2">A finished batch can’t take more activities.</p>
        </>
      ) : (
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-sm font-semibold">Activity</legend>
          {ACTIVITIES.map(([v, label]) => (
            <label key={v} className={`${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`}>
              <input type="radio" value={v} className="accent-leaf-700" {...register('type')} /> {label}
            </label>
          ))}
        </fieldset>
      )}
      <Field label="Note (optional)" error={e.note?.message}>
        <input className={`${inputCls} ${touch}`} aria-invalid={!!e.note} placeholder={finishing ? 'e.g. Screened and bagged' : 'e.g. Turned fully, smells fine'} {...register('note')} />
      </Field>
    </Drawer>
  );
}
