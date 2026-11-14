import { useState } from 'react';
import { Link } from 'react-router';
import { OUTGOING_TYPE, outgoingState, useApprovals } from '../../api/approvals';
import { useOutgoing } from '../../api/operations';
import { IncomeChart, Kpi } from '../../components/charts';
import { Badge, btn, PageHeader, Toast } from '../../components/ui';
import { NewOutgoingSheet } from '../operator/OutgoingPage';
import { kg, peso, Period, Table, when } from './shared';

const PERIODS = [['Last 31 days', 31], ['Last 90 days', 90], ['Last 6 months', 183]] as const;
const STATUS = {
  pending: ['warn', 'Waiting for approval'], approved: ['ok', 'Approved'], rejected: ['crit', 'Rejected'],
  recorded: ['ok', 'Recorded · to review'], reversed: ['crit', 'Reversed'],
} as const;

export default function OutgoingPage() {
  const [days, setDays] = useState(31);
  const v = useOutgoing(days);
  const toReview = useApprovals().data?.counts.outgoing_review;
  const [adding, setAdding] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  return (
    <>
      <div className="flex items-start gap-4">
        <PageHeader title="Outgoing and income" sub="Recyclables sold, compost given out, and residual sent for disposal. A reversed sale comes off income on the day it was reversed." />
        <button className={`${btn.base} ${btn.primary} ml-auto shrink-0`} onClick={() => setAdding(true)}>+ Record outgoing</button>
      </div>
      {adding && <NewOutgoingSheet onClose={() => setAdding(false)} onSent={(m) => { setAdding(false); setDone(m); }} />}
      <Toast message={done} />
      {v.data && (
        <>
          <div className="grid grid-cols-5 gap-4">
            <Kpi label="Income this month" value={peso(v.data.income_month)} sub="sales, less any reversed" />
            <Kpi label="Recyclables sold" value={kg(v.data.sold_kg_month)} sub="this month" />
            <Kpi label="Compost given out" value={kg(v.data.compost_kg_month)} sub={`this month · ${kg(v.data.compost_on_hand_kg)} on hand`} />
            <Kpi label="Residual disposed" value={kg(v.data.disposed_kg_month)} sub="this month" />
            <Kpi label="To review" value={toReview === undefined ? '…' : String(toReview)} sub={v.data.pending ? `outgoing · ${v.data.pending} old requests waiting` : 'outgoing records'} />
          </div>
          <section aria-label="Income per month" className="rounded-xl border border-line bg-white p-4">
            <div className="mb-2 flex items-baseline">
              <h3 className="text-sm font-bold">Income per month, last 6 months</h3>
              <Link to="/admin/approvals?tab=outgoing_review" className="ml-auto text-xs font-semibold text-leaf-700 underline">Approvals</Link>
            </div>
            <IncomeChart data={v.data.income_6m} />
          </section>
        </>
      )}
      <Period value={days} options={PERIODS} onChange={setDays} />
      <Table label="Outgoing records" head={['No.', 'Requested', 'Type', 'Material', 'Weight', 'Recipient', 'Total', 'Status', 'Decided by']}
        state={{ isPending: v.isPending, error: v.error, count: v.data?.records.length }} empty="No outgoing records in this period.">
        {v.data?.records.map((o) => (
          <tr key={o.id}>
            <td className="font-semibold whitespace-nowrap">{o.code}</td>
            <td className="whitespace-nowrap text-ink-2">{when(o.requested_at)}</td>
            <td>{OUTGOING_TYPE[o.type]}</td>
            <td>{o.material}{o.area ? ` · ${o.area}` : ''}</td>
            <td className="whitespace-nowrap">{kg(o.kg)}</td>
            <td>{o.recipient}</td>
            <td className="whitespace-nowrap">{o.total === null ? '—' : peso(o.total)}</td>
            <td><span title={o.comment}><Badge kind={STATUS[outgoingState(o)][0]}>{STATUS[outgoingState(o)][1]}</Badge></span></td>
            <td className="whitespace-nowrap text-ink-2">{o.decided_by ?? '—'}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}
