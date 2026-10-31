import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { downloadExport, useExportView, useRecentReports } from '../../api/reports';
import { btn, Drawer, PageHeader } from '../../components/ui';
import { Table, when } from '../operations/shared';
import { Granted } from './shared';

const dayLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' });

export default function ReportsPage() {
  return (
    <>
      <PageHeader title="Reports" sub="Reports shared with you." />
      <Granted screen="reports" what="reports"><Exports /></Granted>
    </>
  );
}

function Exports() {
  const recent = useRecentReports();
  const download = useMutation({ mutationFn: downloadExport });
  const [viewing, setViewing] = useState<number | null>(null);
  return (
    <>
      {download.error && <p role="alert" className="text-sm text-crit">{download.error.message}</p>}
      <Table label="Exported reports" head={['Report', 'Range', 'Format', 'Created by', 'Created', '']}
        state={{ isPending: recent.isPending, error: recent.error, count: recent.data?.length }} empty="No reports exported yet.">
        {recent.data?.map((r) => (
          <tr key={r.id}>
            <td className="font-semibold">{r.title}</td>
            <td className="whitespace-nowrap">{r.kind === 'inventory' ? 'As of export' : `${dayLabel(r.from_day)} – ${dayLabel(r.to_day)}`}</td>
            <td>{r.format.toUpperCase()}</td>
            <td>{r.by}</td>
            <td className="whitespace-nowrap">{when(r.created_at)}</td>
            <td className="whitespace-nowrap text-right">
              <button className={`${btn.base} ${btn.secondary} ${btn.small} mr-2`} onClick={() => setViewing(r.id)}>View</button>
              <button className={`${btn.base} ${btn.secondary} ${btn.small}`} disabled={download.isPending} onClick={() => download.mutate(r.id)}>Download</button>
            </td>
          </tr>
        ))}
      </Table>
      {viewing !== null && <ExportSheet id={viewing} onClose={() => setViewing(null)} />}
    </>
  );
}

function ExportSheet({ id, onClose }: { id: number; onClose: () => void }) {
  const r = useExportView(id);
  return (
    <Drawer title={r.data?.title ?? 'Report'} onClose={onClose} footer={<button className={`${btn.base} ${btn.secondary}`} onClick={onClose}>Close</button>}>
      {r.data?.subtitle && <p className="text-sm text-ink-2">{r.data.subtitle}</p>}
      {r.data && (
        <dl className="flex flex-wrap gap-3">
          {r.data.summary.map(([k, v]) => (
            <div key={k} className="rounded-xl border border-line px-3 py-2">
              <dt className="text-xs text-muted">{k}</dt>
              <dd className="font-extrabold">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      <Table label="Report rows" head={r.data?.columns ?? ['Report']} state={{ isPending: r.isPending, error: r.error, count: r.data?.rows.length }}
        empty="No records in this report.">
        {r.data?.rows.map((row, i) => (
          <tr key={i}>
            {row.map((c, j) => <td key={j} className={typeof c === 'number' ? 'tabular-nums' : ''}>{c === '' ? '—' : c.toLocaleString()}</td>)}
          </tr>
        ))}
      </Table>
      {r.data && r.data.total_rows > r.data.rows.length && (
        <p className="text-xs text-muted">Showing the first {r.data.rows.length} of {r.data.total_rows} rows. The download has all of them.</p>
      )}
    </Drawer>
  );
}
