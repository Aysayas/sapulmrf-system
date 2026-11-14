import { useState } from 'react';
import { useSearchParams } from 'react-router';
import {
  OUTGOING_TYPE, useApprovals, useChangeReviews, useDecide, useReview, useReviewOutgoing, useWeightReviews,
  type Adjustment, type Counts, type Outgoing,
} from '../../api/approvals';
import { useDecideFlag, useFlags } from '../../api/insights';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, peso, Table, when } from '../operations/shared';

const TABS: [keyof Counts, string][] = [
  ['outgoing_review', 'Outgoing to review'],
  ['outgoing', 'Old outgoing requests'],
  ['adjustments', 'Adjustments'],
  ['weights', 'Corrected weights'],
  ['classifications', 'Corrected classifications'],
  ['flagged', 'Flagged records'],
];
const small = `${btn.base} ${btn.small}`;
type Open = { kind: 'outgoing'; row: Outgoing } | { kind: 'adjustments'; row: Adjustment };

export default function ApprovalsPage() {
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find(([k]) => k === params.get('tab'))?.[0] ?? 'outgoing_review') as keyof Counts;
  const inbox = useApprovals();
  const [open, setOpen] = useState<Open | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const state = { isPending: inbox.isPending, error: inbox.error };

  return (
    <>
      <PageHeader title="Approvals" sub="Everything waiting for your decision, in one place." />
      <div role="tablist" aria-label="Approvals" className="flex gap-1 border-b border-line">
        {TABS.filter(([key]) => key !== 'outgoing' || tab === key || inbox.data?.counts.outgoing).map(([key, label]) => (  // old requests: only while some wait
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setParams({ tab: key })}
            className={`-mb-px flex items-center gap-1.5 border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${tab === key ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`}>
            {label}
            <span className={`rounded-full px-1.5 text-[11px] font-bold ${inbox.data?.counts[key] ? 'bg-leaf-700 text-white' : 'bg-surface-2 text-muted'}`}>
              {inbox.data?.counts[key] ?? '·'}
            </span>
          </button>
        ))}
      </div>

      {tab === 'outgoing_review' && <OutgoingReviews rows={inbox.data?.outgoing_review} state={state} onDone={setToast} />}

      {tab === 'outgoing' && (
        <Table label="Outgoing waiting for approval" head={['No.', 'Requested', 'Type', 'Material', 'Recipient', 'Total', 'Requested by', '']}
          state={{ ...state, count: inbox.data?.outgoing.length }} empty="No outgoing records waiting.">
          {inbox.data?.outgoing.map((o) => (
            <tr key={o.id}>
              <td className="font-semibold">{o.code}</td>
              <td className="whitespace-nowrap text-ink-2">{when(o.requested_at)}</td>
              <td>{OUTGOING_TYPE[o.type]}</td>
              <td className="whitespace-nowrap">{o.material} · {kg(o.kg)}</td>
              <td>{o.recipient}</td>
              <td>{o.total === null ? '—' : peso(o.total)}</td>
              <td className="text-ink-2">{o.requested_by ?? '—'}</td>
              <td><button className={`${small} ${btn.secondary}`} aria-label={`Review ${o.code}`} onClick={() => setOpen({ kind: 'outgoing', row: o })}>Review</button></td>
            </tr>
          ))}
        </Table>
      )}

      {tab === 'adjustments' && (
        <Table label="Adjustments waiting for approval" head={['Requested', 'Material', 'Storage area', 'System said', 'Counted', 'Reason', 'Requested by', '']}
          state={{ ...state, count: inbox.data?.adjustments.length }} empty="No adjustments waiting.">
          {inbox.data?.adjustments.map((a) => (
            <tr key={a.id}>
              <td className="whitespace-nowrap text-ink-2">{when(a.requested_at)}</td>
              <td className="font-semibold">{a.material}</td>
              <td>{a.area}</td>
              <td>{kg(a.system_kg)}</td>
              <td>{kg(a.actual_kg)}</td>
              <td>{a.reason}</td>
              <td className="text-ink-2">{a.requested_by ?? '—'}</td>
              <td><button className={`${small} ${btn.secondary}`} aria-label={`Review adjustment of ${a.material} in ${a.area}`} onClick={() => setOpen({ kind: 'adjustments', row: a })}>Review</button></td>
            </tr>
          ))}
        </Table>
      )}

      {tab === 'weights' && <WeightReviews onDone={setToast} />}
      {tab === 'classifications' && <ChangeReviews onDone={setToast} />}
      {tab === 'flagged' && <FlaggedRecords onDone={setToast} />}

      {open && <DecisionDrawer open={open} onClose={() => setOpen(null)} onDone={(m) => { setOpen(null); setToast(m); }} />}
      <Toast message={toast} />
    </>
  );
}

function DecisionDrawer({ open, onClose, onDone }: { open: Open; onClose: () => void; onDone: (message: string) => void }) {
  const decide = useDecide();
  const [comment, setComment] = useState('');
  const { kind, row } = open;
  const name = kind === 'outgoing' ? `${row.code} · ${OUTGOING_TYPE[row.type]}` : `Adjustment · ${row.material}, ${row.area}`;
  const short = kind === 'outgoing' && row.available_kg! < row.kg;

  const [needReason, setNeedReason] = useState(false);
  const send = (decision: 'approve' | 'reject') =>
    decision === 'reject' && !comment.trim() ? setNeedReason(true) : decide.mutate({ kind, id: row.id, decision, comment: comment.trim() }, {
      onSuccess: () => onDone(decision === 'reject' ? `${kind === 'outgoing' ? row.code : 'Adjustment'} rejected` : approvedMessage(open)),
    });

  const facts: [string, string][] = kind === 'outgoing'
    ? [
        ['Material', row.material],
        ['From', row.area ? `${row.area} · ${kg(row.available_kg!)} in stock` : `Finished compost · ${kg(row.available_kg!)} on hand`],
        ['Quantity', kg(row.kg)],
        [row.type === 'sale' ? 'Buyer' : 'Recipient', row.recipient],
        ...(row.price_per_kg !== null ? [['Price per kg', peso(row.price_per_kg)], ['Total', peso(row.total ?? 0)]] as [string, string][] : []),
      ]
    : [
        ['Material and area', `${row.material} · ${row.area}`],
        ['System said', `${kg(row.system_kg)} when requested (${kg(row.current_kg)} now)`],
        ['Actual count', kg(row.actual_kg)],
        ['Reason', row.reason],
        ...(row.details ? [['Details', row.details]] as [string, string][] : []),
      ];

  return (
    <Drawer title={name} onClose={onClose} footer={
      <>
        <button className={`${btn.base} ${btn.secondary}`} disabled={decide.isPending} onClick={() => send('reject')}>Reject</button>
        <button className={`${btn.base} ${btn.primary}`} disabled={decide.isPending || short} onClick={() => send('approve')}>
          {kind === 'outgoing' && row.type === 'sale' ? 'Approve sale' : 'Approve'}
        </button>
      </>
    }>
      <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 text-sm">
        {facts.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-2">{k}</dt>
            <dd className="font-semibold">{v}</dd>
          </div>
        ))}
        <dt className="text-ink-2">Requested by</dt>
        <dd>{row.requested_by ?? '—'} · {when(row.requested_at)}</dd>
      </dl>
      <p className={`rounded-lg px-3 py-2 text-sm ${short ? 'bg-crit-100 text-crit' : 'bg-surface'}`}>{afterApproval(open)}</p>
      <label className="text-sm font-semibold">
        Comment <span className="font-normal text-muted">(optional; say why if you reject)</span>
        <textarea className={`${inputCls} mt-1`} rows={3} maxLength={200} value={comment} aria-invalid={needReason && !comment.trim()}
          onChange={(e) => setComment(e.target.value)} />
      </label>
      {needReason && !comment.trim() && <p role="alert" className="text-sm text-crit">Say why you are rejecting it.</p>}
      {decide.error && <p role="alert" className="text-sm text-crit">{decide.error.message}</p>}
    </Drawer>
  );
}

function afterApproval({ kind, row }: Open) {
  if (kind === 'outgoing' && row.available_kg! < row.kg) return `Only ${kg(row.available_kg!)} available. Reject it, or ask the operator for a new count.`;
  if (kind === 'outgoing' && row.area === null) return `After approval: compost on hand ${kg(row.available_kg!)} → ${kg(row.available_kg! - row.kg)}`;
  const after = row.area_after_kg ?? 0;
  const cap = row.capacity_kg ?? 0;
  return `After approval: ${row.area} ${kg(row.area_kg ?? 0)} → ${kg(after)} (${cap ? Math.round((after / cap) * 100) : 0}% full)`;
}

function approvedMessage({ kind, row }: Open) {
  if (kind === 'adjustments') return `Adjustment approved · ${row.material} in ${row.area} is now ${kg(row.actual_kg)}`;
  return `${row.code} approved · ${kg(row.kg)} left ${row.area ?? 'compost'}${row.total !== null ? ' · income recorded' : ''}`;
}

function WeightReviews({ onDone }: { onDone: (m: string) => void }) {
  const list = useWeightReviews();
  const review = useReview();
  const mark = (id: number, code: string, r: 'ok' | 'recheck') =>
    review.mutate({ kind: 'weights', id, review: r }, { onSuccess: () => onDone(`${code} marked ${r === 'ok' ? 'OK' : 'to recheck'}`) });
  return (
    <Table label="Corrected weights" head={['Delivery', 'Received', 'Source area', 'Scale said', 'Corrected to', 'Reason', 'By', '']}
      state={{ isPending: list.isPending, error: list.error ?? review.error, count: list.data?.length }} empty="No corrected weights to review.">
      {list.data?.map((d) => (
        <tr key={d.id}>
          <td className="font-semibold">{d.code}</td>
          <td className="whitespace-nowrap text-ink-2">{when(d.received_at)}</td>
          <td>{d.source_area}</td>
          <td>{kg(d.scale_kg ?? 0)}</td>
          <td className="font-semibold">{kg(d.weight_kg)}</td>
          <td>{d.correction_reason}</td>
          <td className="text-ink-2">{d.recorded_by ?? '—'}</td>
          <td className="whitespace-nowrap">
            <button className={`${small} ${btn.primary}`} aria-label={`Mark ${d.code} OK`} disabled={review.isPending} onClick={() => mark(d.id, d.code, 'ok')}>OK</button>{' '}
            <button className={`${small} ${btn.secondary}`} aria-label={`Ask to recheck ${d.code}`} disabled={review.isPending} onClick={() => mark(d.id, d.code, 'recheck')}>Ask to recheck</button>
          </td>
        </tr>
      ))}
    </Table>
  );
}

function FlaggedRecords({ onDone }: { onDone: (m: string) => void }) {
  const list = useFlags();
  const decide = useDecideFlag();
  const mark = (id: number, code: string, d: 'valid' | 'incorrect') =>
    decide.mutate({ id, decision: d }, { onSuccess: () => onDone(`${code} marked ${d === 'valid' ? 'valid' : 'a false alarm'}`) });
  const busy = (id: number) => decide.isPending && decide.variables?.id === id;   // only the row being decided waits
  return (
    <>
      {decide.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{decide.error.message}</p>}
      <p className="text-sm text-ink-2">Flagged records are never changed automatically. Valid means the weight really is unusual, and it stays out of the usual weights. False alarm means the weight is normal, and it counts toward them. To fix a wrong weight, use a problem report.</p>
      <Table label="Flagged records" head={['Record', 'Source', 'Value', 'Expected', 'Why flagged', 'Your decision']}
        state={{ isPending: list.isPending, error: list.error, count: list.data?.length }} empty="No flagged records to review.">
        {list.data?.map((f) => (
          <tr key={f.id}>
            <td className="font-semibold whitespace-nowrap">{f.code}<span className="block text-xs font-normal text-muted">{when(f.received_at)}</span></td>
            <td>{f.source_area} · {f.category}</td>
            <td className="whitespace-nowrap">{kg(f.value_kg)}{f.kind === 'gap' ? ' received' : ''}</td>
            <td>{f.expected}</td>
            <td><Badge kind="warn">{f.why}</Badge></td>
            <td className="whitespace-nowrap">
              <button className={`${small} ${btn.secondary}`} aria-label={`Mark ${f.code} valid`} disabled={busy(f.id)} onClick={() => mark(f.id, f.code, 'valid')}>Valid</button>{' '}
              <button className={`${small} ${btn.secondary}`} aria-label={`Mark ${f.code} a false alarm`} disabled={busy(f.id)} onClick={() => mark(f.id, f.code, 'incorrect')}>False alarm</button>
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}

function ChangeReviews({ onDone }: { onDone: (m: string) => void }) {
  const list = useChangeReviews();
  const review = useReview();
  const mark = (id: number, r: 'ok' | 'wrong') =>
    review.mutate({ kind: 'classifications', id, review: r }, { onSuccess: () => onDone(r === 'ok' ? 'Change marked OK' : 'Change marked wrong') });
  return (
    <Table label="Corrected classifications" head={['Time', 'Photo', 'Camera said', 'Operator changed to', 'Reason', 'By', '']}
      state={{ isPending: list.isPending, error: list.error ?? review.error, count: list.data?.length }} empty="No changed classifications to review.">
      {list.data?.map((c) => (
        <tr key={c.id}>
          <td className="whitespace-nowrap text-ink-2">{when(c.confirmed_at ?? c.suggested_at)}</td>
          <td>{c.image_url && <img src={c.image_url} alt={`Item the camera called ${c.suggested}`} className="h-10 w-14 rounded object-cover" loading="lazy" />}</td>
          <td className="whitespace-nowrap">{c.suggested} · {Math.round(c.confidence * 100)}%</td>
          <td><Badge kind="warn">{c.final}</Badge></td>
          <td>{c.reason || '—'}</td>
          <td className="text-ink-2">{c.confirmed_by ?? '—'}</td>
          <td className="whitespace-nowrap">
            <button className={`${small} ${btn.primary}`} aria-label={`Mark change to ${c.final} OK`} disabled={review.isPending} onClick={() => mark(c.id, 'ok')}>OK</button>{' '}
            <button className={`${small} ${btn.secondary}`} aria-label={`Mark change to ${c.final} wrong`} disabled={review.isPending} onClick={() => mark(c.id, 'wrong')}>Wrong</button>
          </td>
        </tr>
      ))}
    </Table>
  );
}

/** Sales and give-outs operators recorded at the kiosk: they already left stock. OK them, or reverse one (stock goes back today). */
function OutgoingReviews({ rows, state, onDone }: { rows: Outgoing[] | undefined; state: { isPending: boolean; error: Error | null }; onDone: (m: string) => void }) {
  const review = useReviewOutgoing();
  const [reversing, setReversing] = useState<number | null>(null);
  const [why, setWhy] = useState('');
  const busy = (id: number) => review.isPending && review.variables?.id === id;
  const send = (o: Outgoing, decision: 'ok' | 'reverse') =>
    review.mutate({ id: o.id, decision, comment: decision === 'reverse' ? why.trim() : '' }, {
      onSuccess: () => { setReversing(null); setWhy(''); onDone(decision === 'ok' ? `${o.code} marked OK` : `${o.code} reversed · stock is back`); },
    });
  return (
    <>
      {review.error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{review.error.message}</p>}
      <Table label="Outgoing to review" head={['No.', 'When', 'Type', 'Material', 'Recipient', 'Total', 'Recorded by', '']}
        state={{ ...state, count: rows?.length }} empty="Nothing to review. Sales and give-outs from the kiosk show here.">
        {rows?.map((o) => (
          <tr key={o.id}>
            <td className="font-semibold">{o.code}</td>
            <td className="whitespace-nowrap text-ink-2">{when(o.decided_at ?? o.requested_at)}</td>
            <td>{OUTGOING_TYPE[o.type]}</td>
            <td className="whitespace-nowrap">{o.material}{o.area ? ` · ${o.area}` : ''} · {kg(o.kg)}</td>
            <td>{o.recipient}</td>
            <td>{o.total === null ? '—' : peso(o.total)}</td>
            <td className="text-ink-2">{o.requested_by ?? '—'}</td>
            <td className="whitespace-nowrap">
              {reversing === o.id ? (
                <span className="flex items-center gap-1.5">
                  <input aria-label={`Why reverse ${o.code}`} className={`${inputCls} w-48`} placeholder="Why? e.g. buyer returned it"
                    value={why} onChange={(e) => setWhy(e.target.value)} maxLength={200} autoFocus />
                  <button className={`${small} ${btn.primary}`} disabled={!why.trim() || busy(o.id)} onClick={() => send(o, 'reverse')}>Reverse</button>
                  <button className={`${small} ${btn.secondary}`} onClick={() => { setReversing(null); setWhy(''); }}>Cancel</button>
                </span>
              ) : (
                <span className="flex gap-1.5">
                  <button className={`${small} ${btn.primary}`} aria-label={`Mark ${o.code} OK`} disabled={busy(o.id)} onClick={() => send(o, 'ok')}>OK</button>
                  <button className={`${small} ${btn.secondary}`} aria-label={`Reverse ${o.code}`} disabled={busy(o.id)} onClick={() => setReversing(o.id)}>Reverse…</button>
                </span>
              )}
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}
