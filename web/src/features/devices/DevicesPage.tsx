import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ApiError } from '../../api/client';
import { TYPE_LABEL, useDevices, useNewDeviceKey, useRegisterDevice, useUpdateDevice, type Device, type DeviceWithKey } from '../../api/devices';
import { Badge, btn, Drawer, inputCls, Toast } from '../../components/ui';

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' }) : 'Never';

const STATUS = {
  online: <Badge kind="ok">● Online</Badge>,
  offline: <Badge kind="crit">○ Offline</Badge>,
  never: <Badge kind="dash">Never connected</Badge>,
};

export default function DevicesPage() {
  const devices = useDevices();
  const [editing, setEditing] = useState<Device | 'new' | null>(null);
  const [shownKey, setShownKey] = useState<DeviceWithKey | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  return (
    <>
      <div className="flex items-center">
        <p className="text-sm text-ink-2">Status refreshes every 30 seconds. A device is online if it checked in within the last 2 minutes.</p>
        <button className={`${btn.base} ${btn.primary} ml-auto`} onClick={() => setEditing('new')}>
          + Register device
        </button>
      </div>
      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              {['Device ID', 'Type', 'Location', 'Status', 'Last seen', ''].map((h) => (
                <th key={h} className="px-3 py-2 font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {devices.isPending && <tr><td colSpan={6} className="px-3 py-4 text-muted">Loading…</td></tr>}
            {devices.isError && <tr><td colSpan={6} className="px-3 py-4 text-crit">{devices.error.message}</td></tr>}
            {devices.data?.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-4 text-ink-2">No devices yet. Register the kiosk.</td></tr>
            )}
            {devices.data?.map((d) => (
              <tr key={d.id} className={`border-b border-line/60 last:border-0 ${d.active ? '' : 'text-muted'}`}>
                <td className="px-3 py-2.5 font-semibold">{d.code}</td>
                <td className="px-3 py-2.5">{TYPE_LABEL[d.type]}</td>
                <td className="px-3 py-2.5">{d.location || '—'}</td>
                <td className="px-3 py-2.5">{d.active ? STATUS[d.status] : <Badge kind="dash">Deactivated</Badge>}</td>
                <td className="px-3 py-2.5 text-ink-2">{when(d.last_seen_at)}</td>
                <td className="px-3 py-2.5 text-right">
                  <button className={`${btn.base} ${btn.secondary} ${btn.small}`} aria-label={`Edit ${d.code}`} onClick={() => setEditing(d)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <DeviceDrawer
          device={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(msg) => {
            setEditing(null);
            setToast(msg);
          }}
          onKey={(d) => {
            setEditing(null);
            setShownKey(d);
          }}
        />
      )}
      {shownKey && <KeyPanel device={shownKey} onClose={() => setShownKey(null)} />}
      <Toast message={toast} />
    </>
  );
}

const schema = z.object({
  code: z.string().trim().regex(/^[A-Za-z0-9-]{2,20}$/, '2–20 letters, numbers or dashes, like KIOSK-01.'),
  type: z.enum(['weighing_station', 'compost_sensor', 'sorting_camera']),
  location: z.string().trim().max(80),
  active: z.boolean(),
});
type Form = z.infer<typeof schema>;

function DeviceDrawer({ device, onClose, onSaved, onKey }: { device: Device | null; onClose: () => void; onSaved: (m: string) => void; onKey: (d: DeviceWithKey) => void }) {
  const registerDevice = useRegisterDevice();
  const update = useUpdateDevice();
  const newKey = useNewDeviceKey();
  const [confirmKey, setConfirmKey] = useState(false);
  const busy = registerDevice.isPending || update.isPending || newKey.isPending;
  const error = registerDevice.error ?? update.error ?? newKey.error;
  const { register, handleSubmit, formState, setError } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { code: device?.code ?? '', type: device?.type ?? 'weighing_station', location: device?.location ?? '', active: device?.active ?? true },
  });
  const on409 = (e: Error) => e instanceof ApiError && e.status === 409 && setError('code', { message: e.message });

  const onSubmit = (f: Form) =>
    device
      ? update.mutate({ id: device.id, ...f }, { onSuccess: (d) => onSaved(`${d.code} saved`), onError: on409 })
      : registerDevice.mutate({ code: f.code, type: f.type, location: f.location }, { onSuccess: onKey, onError: on409 });

  return (
    <Drawer
      title={device ? `Edit ${device.code}` : 'Register device'}
      onClose={onClose}
      footer={
        <>
          <button className={`${btn.base} ${btn.secondary}`} onClick={onClose}>Cancel</button>
          <button className={`${btn.base} ${btn.primary}`} disabled={busy} onClick={handleSubmit(onSubmit)}>
            {device ? 'Save changes' : 'Register'}
          </button>
        </>
      }
    >
      {error && !(error instanceof ApiError && error.status === 409) && (
        <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{error.message}</p>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Device ID
        <input {...register('code')} placeholder="e.g. KIOSK-02" className={`${inputCls} uppercase`} aria-invalid={!!formState.errors.code} />
        {formState.errors.code && <span className="text-xs text-crit">{formState.errors.code.message}</span>}
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Location
        <input {...register('location')} placeholder="e.g. Intake area" className={inputCls} />
      </label>
      {!device && <p className="text-sm text-ink-2">After you register, the device key is shown once. Copy it into the device so it can check in.</p>}
      {device && (
        <>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" {...register('active')} className="accent-leaf-700" />
            Active <span className="text-xs text-muted">A deactivated device can’t check in.</span>
          </label>
          <div className="rounded-lg border border-line p-3 text-sm">
            <b>Device key</b>
            <p className="mt-1 text-ink-2">Lost the key, or think someone else has it? A new key stops the old one working right away.</p>
            {!confirmKey ? (
              <button className={`${btn.base} ${btn.secondary} ${btn.small} mt-2`} onClick={() => setConfirmKey(true)}>
                Generate new key
              </button>
            ) : (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs font-semibold text-warn">The device stops connecting until you update it.</span>
                <button className={`${btn.base} ${btn.primary} ${btn.small}`} disabled={busy} onClick={() => newKey.mutate(device.id, { onSuccess: onKey })}>
                  Yes, generate
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </Drawer>
  );
}

function KeyPanel({ device, onClose }: { device: DeviceWithKey; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <>
      <div className="fixed inset-0 z-20 bg-leaf-900/35" />
      <div role="dialog" aria-modal="true" aria-label={`Key for ${device.code}`} className="fixed top-1/2 left-1/2 z-20 flex w-[520px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="text-lg font-bold">Key for {device.code}</h2>
        <p className="text-sm text-ink-2">Put this key in the device’s settings. It sends it in the <code>X-Device-Key</code> header when it checks in.</p>
        <code aria-label="Device key" className="rounded-lg bg-surface-2 px-3 py-2 font-mono text-sm break-all">{device.key}</code>
        <p className="rounded-lg bg-warn-100 px-3 py-2 text-sm font-semibold text-warn">You won’t see this key again. Copy it now.</p>
        <div className="flex justify-end gap-2">
          <button
            className={`${btn.base} ${btn.secondary}`}
            onClick={() => navigator.clipboard.writeText(device.key).then(() => setCopied(true))}
          >
            {copied ? 'Copied ✓' : 'Copy key'}
          </button>
          <button className={`${btn.base} ${btn.primary}`} onClick={onClose}>Done</button>
        </div>
      </div>
    </>
  );
}
