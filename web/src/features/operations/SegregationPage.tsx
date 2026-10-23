import { useState } from 'react';
import { useCompliance } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { kg, PctBar, Period, Table } from './shared';

const PERIODS = [['Last 7 days', 7], ['Last 30 days', 30], ['Last 90 days', 90]] as const;

export default function SegregationPage() {
  const [days, setDays] = useState(30);
  const c = useCompliance(days);
  return (
    <>
      <PageHeader title="Segregation compliance" sub="How many deliveries from each source area arrived already segregated" />
      <Period value={days} options={PERIODS} onChange={setDays} />
      {c.data && (
        <div className="grid grid-cols-4 gap-4">
          <Kpi label="Compliance" value={`${c.data.pct}%`} sub={`${c.data.segregated} of ${c.data.deliveries} checked deliveries`} />
          <Kpi label="Deliveries checked" value={String(c.data.deliveries)} />
          <Kpi label="Arrived segregated" value={String(c.data.segregated)} />
          <Kpi label="Wet waste separated" value={kg(c.data.wet_kg_separated)} sub="from mixed deliveries" />
        </div>
      )}
      <Table label="Compliance by source area" head={['Source area', 'Deliveries checked', 'Arrived segregated', 'Compliance']}
        state={{ isPending: c.isPending, error: c.error, count: c.data?.rows.length }} empty="No checked deliveries in this period.">
        {c.data?.rows.map((r) => (
          <tr key={r.source_area}>
            <td className="font-semibold">{r.source_area}</td>
            <td>{r.deliveries}</td>
            <td>{r.segregated}</td>
            <td><PctBar pct={r.pct} label={`${r.source_area} compliance`} /></td>
          </tr>
        ))}
      </Table>
    </>
  );
}
