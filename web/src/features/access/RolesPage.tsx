import { useMemo, useState } from 'react';
import { useAccess, useSaveAccess, type Screen } from '../../api/access';
import { btn, Toast } from '../../components/ui';

const ROLES = [
  ['Barangay Administrator', 'Manages accounts, settings and approvals. Fixed.'],
  ['MRF Operator', 'Records the daily MRF work. Fixed.'],
  ['Authorized Barangay Staff', 'View only. The screens below are turned on per person.'],
];

export default function RolesPage() {
  const access = useAccess();
  const save = useSaveAccess();
  const [edits, setEdits] = useState<Record<number, Partial<Record<Screen, boolean>>>>({});
  const [toast, setToast] = useState<string | null>(null);
  const changed = useMemo(() => Object.entries(edits).filter(([, g]) => Object.keys(g).length), [edits]);

  const isOn = (userId: number, s: Screen) =>
    edits[userId]?.[s] ?? access.data!.staff.find((p) => p.user_id === userId)!.grants[s];

  const toggle = (userId: number, s: Screen) => {
    const original = access.data!.staff.find((p) => p.user_id === userId)!.grants[s];
    const next = !isOn(userId, s);
    setEdits((e) => {
      const g = { ...e[userId] };
      if (next === original) delete g[s];
      else g[s] = next;
      return { ...e, [userId]: g };
    });
  };

  const onSave = () =>
    save.mutate(changed.map(([id, grants]) => ({ userId: Number(id), grants })), {
      onSuccess: () => {
        setEdits({});
        setToast('Staff access saved');
      },
    });

  return (
    <>
      <div className="grid grid-cols-3 gap-4">
        {ROLES.map(([name, desc]) => (
          <div key={name} className="rounded-xl border border-line bg-white p-4">
            <h3 className="text-sm font-bold">{name}</h3>
            <p className="mt-1 text-xs text-ink-2">{desc}</p>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-line bg-white p-4">
        <h3 className="mb-3 text-sm font-bold">Staff access, per person</h3>
        {access.isPending && <p className="text-muted">Loading…</p>}
        {access.isError && <p className="text-crit">{access.error.message}</p>}
        {access.data && access.data.staff.length === 0 && (
          <p className="text-ink-2">No staff accounts yet. Add one in Settings › Users with the role Authorized Barangay Staff.</p>
        )}
        {access.data && access.data.staff.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="px-3 py-2 font-semibold">Screen</th>
                {access.data.staff.map((p) => (
                  <th key={p.user_id} className="px-3 py-2 text-center font-semibold">
                    {p.name}
                    {!p.active && <span className="block font-normal">(disabled)</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {access.data.screens.map((s) => (
                <tr key={s.key} className="border-b border-line/60 last:border-0">
                  <td className="px-3 py-2.5">{s.label}</td>
                  {access.data.staff.map((p) => (
                    <td key={p.user_id} className="px-3 py-2.5 text-center">
                      <input
                        type="checkbox"
                        className="size-4 accent-leaf-700"
                        aria-label={`${s.label} for ${p.name}`}
                        checked={isOn(p.user_id, s.key)}
                        onChange={() => toggle(p.user_id, s.key)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {save.error && <p role="alert" className="text-sm font-semibold text-crit">{save.error.message}</p>}
      <div className="flex items-center gap-3">
        <button className={`${btn.base} ${btn.primary}`} disabled={!changed.length || save.isPending} onClick={onSave}>
          Save access
        </button>
        {changed.length > 0 && <span className="text-sm text-ink-2">Unsaved changes for {changed.length} person{changed.length > 1 ? 's' : ''}</span>}
      </div>
      <Toast message={toast} />
    </>
  );
}
