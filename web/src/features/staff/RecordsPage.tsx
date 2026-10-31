import { useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import { useMyAccess, type Screen } from '../../api/access';
import { OUTGOING_TYPE } from '../../api/approvals';
import { useOutgoing } from '../../api/operations';
import { Badge, PageHeader } from '../../components/ui';
import CameraPage from '../operations/CameraPage';
import CompostPage from '../operations/CompostPage';
import IntakePage from '../operations/IntakePage';
import InventoryPage from '../operations/InventoryPage';
import SegregationPage from '../operations/SegregationPage';
import { kg, Period, Table, when } from '../operations/shared';
import { Granted } from './shared';

const TABS: { key: string; label: string; grant?: Screen; what?: string; page: ReactNode }[] = [
  { key: 'intake', label: 'Intake', page: <IntakePage /> },
  { key: 'segregation', label: 'Segregation', grant: 'segregation', what: 'segregation records', page: <SegregationPage /> },
  { key: 'inventory', label: 'Inventory', page: <InventoryPage /> },
  { key: 'compost', label: 'Compost', page: <CompostPage /> },
  { key: 'outgoing', label: 'Outgoing', page: <Outgoing /> },
  { key: 'camera', label: 'Live camera', grant: 'camera', what: 'the live camera', page: <CameraPage /> },
];

export default function RecordsPage() {
  const [params, setParams] = useSearchParams();
  const grants = useMyAccess().data?.grants;
  const tab = TABS.find((t) => t.key === params.get('tab')) ?? TABS[0];
  return (
    <>
      <PageHeader title="Records" sub="View only." />
      <div role="tablist" aria-label="Records" className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t} onClick={() => setParams({ tab: t.key })}
            className={`-mb-px min-h-11 border-b-2 px-3.5 text-sm whitespace-nowrap ${tab === t ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`}>
            {t.label}
            {t.grant && grants && !grants[t.grant] && <small className="ml-1 font-normal text-muted">(no access)</small>}
          </button>
        ))}
      </div>
      {/* The reused pages bring their own h1, so it steps down under Records. */}
      <div role="tabpanel" aria-label={tab.label} className="flex flex-col gap-4 [&_h1]:text-lg">
        {tab.grant ? <Granted screen={tab.grant} what={tab.what!}>{tab.page}</Granted> : tab.page}
      </div>
    </>
  );
}

const PERIODS = [['Last 31 days', 31], ['Last 90 days', 90], ['Last 6 months', 183]] as const;
const STATUS = { pending: ['warn', 'Waiting for approval'], approved: ['ok', 'Approved'], rejected: ['crit', 'Rejected'] } as const;

/** Not the admin page: that one shows income, which is no part of the staff view, and links to Approvals. */
function Outgoing() {
  const [days, setDays] = useState(31);
  const v = useOutgoing(days);
  return (
    <>
      <PageHeader title="Outgoing" sub="Recyclables sold, compost given out, and residual sent for disposal." />
      <Period value={days} options={PERIODS} onChange={setDays} />
      <Table label="Outgoing records" head={['No.', 'Requested', 'Type', 'Material', 'Weight', 'Recipient', 'Status']}
        state={{ isPending: v.isPending, error: v.error, count: v.data?.records.length }} empty="No outgoing records in this period.">
        {v.data?.records.map((o) => (
          <tr key={o.id}>
            <td className="font-semibold whitespace-nowrap">{o.code}</td>
            <td className="whitespace-nowrap text-ink-2">{when(o.requested_at)}</td>
            <td>{OUTGOING_TYPE[o.type]}</td>
            <td>{o.material}{o.area ? ` · ${o.area}` : ''}</td>
            <td className="whitespace-nowrap">{kg(o.kg)}</td>
            <td>{o.recipient}</td>
            <td><Badge kind={STATUS[o.status][0]}>{STATUS[o.status][1]}</Badge></td>
          </tr>
        ))}
      </Table>
    </>
  );
}
