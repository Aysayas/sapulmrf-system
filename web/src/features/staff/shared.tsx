import type { ReactNode } from 'react';
import { useMyAccess, type Screen } from '../../api/access';

export function NoAccess({ what }: { what: string }) {
  return (
    <div className="rounded-xl border border-dashed border-edge bg-white px-4 py-12 text-center">
      <b className="block text-lg">You don’t have access to {what}</b>
      <p className="text-sm text-ink-2">Ask the Barangay Administrator to turn it on for your account.</p>
    </div>
  );
}

/** Mounts children only when granted, so no request is sent that the API would refuse. */
export function Granted({ screen, what, children }: { screen: Screen; what: string; children: ReactNode }) {
  const access = useMyAccess();
  if (access.isPending) return <p className="text-muted">Loading…</p>;
  if (access.error) return <p role="alert" className="text-crit">{access.error.message}</p>;
  return access.data.grants[screen] ? children : <NoAccess what={what} />;
}
