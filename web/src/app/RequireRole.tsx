import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { HOME, useMe, type Role } from '../api/auth';

/** Only a logged-in user with `role` gets past this. Others go to their own side. */
export default function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const me = useMe();

  if (me.isPending) return <p className="p-8 text-muted">Loading…</p>;
  if (me.isError) return <p className="p-8 text-crit">Can’t reach the server. Check that Docker is running.</p>;
  if (!me.data) return <Navigate to="/login" replace />;
  if (me.data.role !== role) return <Navigate to={HOME[me.data.role]} replace />;
  return children;
}
