import { useCamera } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { KioskLive } from './KioskLive';
import { kg, Table } from './shared';

/** The kiosk camera is also the sorting-area camera: its live view, then how its sorting suggestions are doing. */
export default function CameraPage() {
  const cam = useCamera();
  return (
    <>
      <PageHeader title="Live camera" sub="The kiosk camera: live view, and how its sorting suggestions are doing" />
      <KioskLive />
      {cam.isPending && <p className="text-muted">Loading…</p>}
      {cam.error && <p role="alert" className="text-crit">{cam.error.message}</p>}
      {cam.data && (
        <div className="grid grid-cols-[1fr_1.4fr] gap-4">
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <Kpi label="Classified today" value={String(cam.data.today)} sub="confirmed by the operator" />
              <Kpi label="Waiting to confirm" value={String(cam.data.pending)} sub="in Operations › Sorting" />
            </div>
            <Kpi label="Camera accepted today" value={`${cam.data.accepted_pct}%`} sub="kept as suggested by the operator" />
          </div>
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-bold">In storage by material</h2>
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
