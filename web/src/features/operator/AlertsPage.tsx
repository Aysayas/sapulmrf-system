import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useAcknowledge, useAlerts, useMyProblems, useReportProblem } from '../../api/alerts';
import { useDevices } from '../../api/devices';
import { useIntake } from '../../api/operations';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { Period, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';

const STATES = [['Open', 'open'], ['Acknowledged', 'acknowledged'], ['Resolved', 'resolved']] as const;
type State = (typeof STATES)[number][1];

export default function AlertsPage() {
  const [state, setState] = useState<State>('open');
  const alerts = useAlerts(state);
  const ack = useAcknowledge();
  const mine = useMyProblems();
  const [reporting, setReporting] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Alerts" sub="Compost out of range, disconnected devices and full storage areas." />
      <button className={`${btn.base} ${btn.secondary} ${touch} w-full`} onClick={() => setReporting(true)}>Report a problem</button>
      <Period value={state} options={STATES} onChange={setState} />
      <ul aria-label="Alerts" className="flex flex-col gap-2">
        {alerts.isPending && <li className="text-muted">Loading…</li>}
        {alerts.data?.length === 0 && <li className="text-muted">No {state} alerts.</li>}
        {alerts.data?.map((a) => (
          <Card key={a.id} label={a.title}>
            <b className="block">{a.title}</b>
            <p className="text-sm text-ink-2">{a.details}</p>
            <p className="text-xs text-muted">Since {when(a.opened_at)}{a.acknowledged_by ? ` · seen by ${a.acknowledged_by}` : ''}</p>
            {!a.acknowledged_at && (
              <button className={`${btn.base} ${btn.primary} ${touch} mt-2 w-full`} disabled={ack.isPending}
                onClick={() => ack.mutate(a.id, { onSuccess: () => setDone(`Acknowledged · ${a.title}`) })}>
                Acknowledge
              </button>
            )}
          </Card>
        ))}
      </ul>
      {ack.error && <p role="alert" className="text-sm text-crit">{ack.error.message}</p>}

      <h2 className="text-lg font-bold">My reports</h2>
      <ul aria-label="My reports" className="flex flex-col gap-2">
        {mine.data?.length === 0 && <li className="text-muted">No problem reports in the last 30 days.</li>}
        {mine.data?.map((r) => (
          <Card key={r.id} label={r.code}>
            <div className="flex items-start gap-2">
              <b className="flex-1">{r.code} · {r.kind === 'device' ? r.device : r.record_ref}</b>
              <StatusBadge status={r.status} />
            </div>
            <p className="text-sm text-ink-2">{r.details}</p>
            <p className="text-xs text-muted">Sent {when(r.reported_at)}{r.resolved_by ? ` · resolved by ${r.resolved_by}` : ''}</p>
            {r.note && <p className="mt-1 text-sm">“{r.note}”</p>}
          </Card>
        ))}
      </ul>

      {reporting && <ReportSheet onClose={() => setReporting(false)} onSent={(m) => { setReporting(false); setDone(m); }} />}
      <Toast message={done} />
    </>
  );
}

// Mirrors ProblemIn on the server.
const schema = z.object({
  kind: z.enum(['device', 'record']),
  device_id: z.number(),
  record_ref: z.string().trim().max(40),
  details: z.string().trim().min(1, 'Say what is wrong.').max(300),
}).superRefine((f, ctx) => {
  if (f.kind === 'device' && !f.device_id) ctx.addIssue({ code: 'custom', path: ['device_id'], message: 'Pick the device.' });
  if (f.kind === 'record' && !f.record_ref) ctx.addIssue({ code: 'custom', path: ['record_ref'], message: 'Say which record, for example D-0139.' });
});
type Form = z.infer<typeof schema>;

function ReportSheet({ onClose, onSent }: { onClose: () => void; onSent: (m: string) => void }) {
  const devices = useDevices();
  const recent = useIntake(3);
  const send = useReportProblem();
  const { register, handleSubmit, formState, watch } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { kind: 'record', device_id: 0, record_ref: '', details: '' },
  });
  const kind = watch('kind');
  const e = formState.errors;

  const onSubmit = (f: Form) =>
    send.mutate({ kind: f.kind, device_id: f.kind === 'device' ? f.device_id : null, record_ref: f.kind === 'record' ? f.record_ref : '', details: f.details },
      { onSuccess: (r) => onSent(`${r.code} sent to the administrator`) });

  return (
    <Drawer title="Report a problem" onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary} ${touch}`} onClick={onClose}>Cancel</button>
        <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={send.isPending} onClick={handleSubmit(onSubmit)}>Send to administrator</button>
      </>
    }>
      {send.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{send.error.message}</p>}
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-semibold">What is wrong?</legend>
        {([['record', 'Incorrect record'], ['device', 'Device problem']] as const).map(([v, label]) => (
          <label key={v} className={`${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`}>
            <input type="radio" value={v} className="accent-leaf-700" {...register('kind')} /> {label}
          </label>
        ))}
      </fieldset>
      {kind === 'device' ? (
        <Field label="Which device?" error={e.device_id?.message}>
          <select className={inputCls} aria-invalid={!!e.device_id} {...register('device_id', { valueAsNumber: true })}>
            <option value={0}>Pick a device</option>
            {devices.data?.filter((d) => d.active).map((d) => (
              <option key={d.id} value={d.id}>{d.code}{d.location ? ` · ${d.location}` : ''} · {d.status}</option>
            ))}
          </select>
        </Field>
      ) : (
        <Field label="Which record?" error={e.record_ref?.message}>
          <input list="recent-records" className={`${inputCls} uppercase`} placeholder="e.g. D-0139" aria-invalid={!!e.record_ref} {...register('record_ref')} />
          <datalist id="recent-records">
            {recent.data?.map((d) => <option key={d.id} value={d.code}>{`${d.source_area} · ${d.weight_kg} kg`}</option>)}
          </datalist>
        </Field>
      )}
      <Field label={kind === 'record' ? 'What should it be?' : 'What is happening?'} error={e.details?.message}>
        <textarea rows={3} className={inputCls} aria-invalid={!!e.details}
          placeholder={kind === 'record' ? 'e.g. Weight should be 4.10 kg, typo' : 'e.g. Scale shows 0 kg with a bag on it'} {...register('details')} />
      </Field>
    </Drawer>
  );
}
