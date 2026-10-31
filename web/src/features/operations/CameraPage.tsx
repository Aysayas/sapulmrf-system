import { useCamera } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { CameraTile } from '../overview/OverviewPage';
import { kg, Table } from './shared';

export default function CameraPage() {
  const cam = useCamera();
  return (
    <>
      <PageHeader title="Live camera" sub="The sorting area camera's latest result, refreshed every 10 seconds" />
      {cam.isPending && <p className="text-muted">Loading…</p>}
      {cam.error && <p role="alert" className="text-crit">{cam.error.message}</p>}
      {cam.data && (
        <div className="grid grid-cols-[2fr_1fr] gap-4">
          <CameraTile c={cam.data.latest} large />
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <Kpi label="Classified today" value={String(cam.data.today)} />
              <Kpi label="Waiting to confirm" value={String(cam.data.pending)} />
            </div>
            <Kpi label="Camera accepted today" value={`${cam.data.accepted_pct}%`} sub="kept as suggested by the operator" />
            <h3 className="-mb-2 text-sm font-bold">In storage by material</h3>
            <Table label="In storage by material" head={['Material', 'Bags', 'Weight']}
              state={{ isPending: false, error: null, count: cam.data.bins.length }} empty="No recyclable materials set up.">
              {cam.data.bins.map((b) => (
                <tr key={b.material}>
                  <td className="font-semibold">{b.material}</td>
                  <td>{b.bags}</td>
                  <td>{kg(b.kg)}</td>
                </tr>
              ))}
            </Table>
          </div>
        </div>
      )}
    </>
  );
}
