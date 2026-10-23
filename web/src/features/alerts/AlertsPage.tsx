import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { useAcknowledge, useAlerts, useAlertSummary, useProblems, useResolveProblem, type Alert, type Problem } from '../../api/alerts';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { Table, when } from '../operations/shared';

const TABS = [
  ['open', 'Open'],
  ['reports', 'Problem reports'],
  ['acknowledged', 'Acknowledged'],
  ['resolved', 'Resolved'],
] as const;
type Tab = (typeof TABS)[number][0];
const KIND = { compost: 'Compost', device: 'Device', storage: 'Storage' } as const;
const small = `${btn.base} ${btn.small}`;

export default function AlertsPage() {
  const [params, setParams] = useSearchParams();
  const tab: Tab = TABS.find(([k]) => k === params.get('tab'))?.[0] ?? 'open';
  const summary = useAlertSummary().data;
  const [toast, setToast] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Alerts" sub="Compost out of range, devices that stopped reporting, storage areas almost full, and problem reports from operators." />
      <div role="tablist" aria-label="Alerts" className="flex gap-1 border-b border-line">
        {TABS.map(([key, label]) => {
          const n = key === 'open' ? summary?.unacknowledged : key === 'reports' ? summary?.open_reports : undefined;
          return (
            <button key={key} role="tab" aria-selected={tab === key} onClick={() => setParams({ tab: key })}
              className={`-mb-px flex items-center gap-1.5 border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${tab === key ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`}>
              {label}
              {n !== undefined && (
                <span className={`rounded-full px-1.5 text-[11px] font-bold ${n ? 'bg-crit text-white' : 'bg-surface-2 text-muted'}`}>{n}</span>
              )}
            </button>
          );
        })}
      </div>
      {tab === 'reports' ? <Reports onDone={setToast} /> : <AlertTable state={tab} onDone={setToast} />}
      <Toast message={toast} />
    </>
  );
}

function AlertTable({ state, onDone }: { state: 'open' | 'acknowledged' | 'resolved'; onDone: (m: string) => void }) {
  const list = useAlerts(state);
  const ack = useAcknowledge();
  const head = state === 'resolved' ? ['Alert', 'Details', 'Since', 'Cleared', 'Seen by'] : ['Alert', 'Details', 'Since', 'Seen by', ''];
  const empty = { open: 'No open alerts. Everything is within its limits.', acknowledged: 'No acknowledged alerts still open.', resolved: 'Nothing cleared in the last 30 days.' }[state];
  return (
    <>
      <Table label={`${state[0].toUpperCase()}${state.slice(1)} alerts`} head={head}
        state={{ isPending: list.isPending, error: list.error ?? ack.error, count: list.data?.length }} empty={empty}>
        {list.data?.map((a: Alert) => (
          <tr key={a.id}>
            <td className="font-semibold"><Badge kind={state === 'resolved' ? 'neutral' : 'crit'}>{KIND[a.kind]}</Badge> {a.title}</td>
            <td>{a.details}</td>
            <td className="whitespace-nowrap text-ink-2">{when(a.opened_at)}</td>
            {state === 'resolved' && <td className="whitespace-nowrap text-ink-2">{when(a.resolved_at!)}</td>}
            <td className="text-ink-2">{a.acknowledged_by ? `${a.acknowledged_by} · ${when(a.acknowledged_at!)}` : '—'}</td>
            {state !== 'resolved' && (
              <td>
                {state === 'open' && (
                  <button className={`${small} ${btn.primary}`} aria-label={`Acknowledge ${a.title}`} disabled={ack.isPending}
                    onClick={() => ack.mutate(a.id, { onSuccess: () => onDone(`${a.title}: acknowledged`) })}>
                    Acknowledge
                  </button>
                )}
              </td>
            )}
          </tr>
        ))}
      </Table>
      {state !== 'resolved' && <p className="text-xs text-muted">An alert stays here until its condition clears, even after it is acknowledged.</p>}
    </>
  );
}

function Reports({ onDone }: { onDone: (m: string) => void }) {
  const [status, setStatus] = useState<'open' | 'resolved'>('open');
  const list = useProblems(status);
  const [open, setOpen] = useState<Problem | null>(null);
  return (
    <>
      <div role="group" aria-label="Report status" className="inline-flex self-start overflow-hidden rounded-lg border border-leaf-700 whitespace-nowrap">
        {(['open', 'resolved'] as const).map((s) => (
          <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)}
            className={`border-r border-leaf-700 px-3.5 py-1.5 text-sm font-semibold last:border-r-0 ${status === s ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`}>
            {s === 'open' ? 'Open' : 'Resolved'}
          </button>
        ))}
      </div>
      <Table label="Problem reports" head={['Report', 'What', 'Device or record', 'Details', 'From', 'When', status === 'open' ? '' : 'Resolution']}
        state={{ isPending: list.isPending, error: list.error, count: list.data?.length }}
        empty={status === 'open' ? 'No open problem reports.' : 'No resolved reports yet.'}>
        {list.data?.map((p) => (
          <tr key={p.id}>
            <td className="font-semibold whitespace-nowrap">{p.code}</td>
            <td>{p.kind === 'device' ? 'Device problem' : 'Incorrect record'}</td>
            <td className="font-semibold">{p.device ?? p.record_ref}</td>
            <td>{p.details}</td>
            <td className="text-ink-2">{p.reported_by ?? '—'}</td>
            <td className="whitespace-nowrap text-ink-2">{when(p.reported_at)}</td>
            <td>
              {status === 'open'
                ? <button className={`${small} ${btn.secondary}`} aria-label={`Resolve ${p.code}`} onClick={() => setOpen(p)}>Resolve</button>
                : <span className="text-ink-2">{p.note} · {p.resolved_by}</span>}
            </td>
          </tr>
        ))}
      </Table>
      {open && <ResolveDrawer report={open} onClose={() => setOpen(null)} onDone={(m) => { setOpen(null); onDone(m); }} />}
    </>
  );
}

function ResolveDrawer({ report, onClose, onDone }: { report: Problem; onClose: () => void; onDone: (m: string) => void }) {
  const resolve = useResolveProblem();
  const [note, setNote] = useState('');
  const [tried, setTried] = useState(false);
  const send = () => (note.trim() ? resolve.mutate({ id: report.id, note: note.trim() }, { onSuccess: () => onDone(`${report.code} resolved`) }) : setTried(true));
  return (
    <Drawer title={`${report.code} · ${report.kind === 'device' ? 'Device problem' : 'Incorrect record'}`} onClose={onClose}
      footer={<button className={`${btn.base} ${btn.primary}`} disabled={resolve.isPending} onClick={send}>Mark resolved</button>}>
      <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 text-sm">
        <dt className="text-ink-2">{report.kind === 'device' ? 'Device' : 'Record'}</dt>
        <dd className="font-semibold">{report.device ?? report.record_ref}</dd>
        <dt className="text-ink-2">What's wrong</dt>
        <dd>{report.details}</dd>
        <dt className="text-ink-2">Reported by</dt>
        <dd>{report.reported_by ?? '—'} · {when(report.reported_at)}</dd>
      </dl>
      {report.kind === 'record' && (
        <p className="rounded-lg bg-surface px-3 py-2 text-sm">Fixing the record itself is a separate step, for example an inventory adjustment. Say what you did in the note.</p>
      )}
      <label className="text-sm font-semibold">
        What was done
        <textarea className={`${inputCls} mt-1`} rows={3} maxLength={200} value={note} aria-invalid={tried && !note.trim()} onChange={(e) => setNote(e.target.value)} />
      </label>
      {tried && !note.trim() && <p role="alert" className="text-sm text-crit">Say what was done before marking it resolved.</p>}
      {resolve.error && <p role="alert" className="text-sm text-crit">{resolve.error.message}</p>}
    </Drawer>
  );
}
