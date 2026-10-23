import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { HOME, ROLE_LABEL, useLogout, useMe, type Role } from '../api/auth';

/** Only a logged-in user with `role` gets past this. Others go to their own side; staff screens aren't built yet. */
export default function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const me = useMe();
  const logout = useLogout();

  if (me.isPending) return <p className="p-8 text-muted">Loading…</p>;
  if (me.isError) return <p className="p-8 text-crit">Can’t reach the server. Check that Docker is running.</p>;
  if (!me.data) return <Navigate to="/login" replace />;
  if (me.data.role === 'staff')
    return (
      <main className="grid min-h-screen place-items-center p-4">
        <div className="max-w-md rounded-2xl bg-white p-8 text-center shadow">
          <h1 className="text-xl font-extrabold">Signed in as {ROLE_LABEL[me.data.role]}</h1>
          <p className="mt-2 text-ink-2">The screens for your role aren’t built yet.</p>
          <button className="mt-4 rounded-lg border border-edge px-4 py-2 font-semibold" onClick={() => logout.mutate()}>
            Log out
          </button>
        </div>
      </main>
    );
  if (me.data.role !== role) return <Navigate to={HOME[me.data.role]} replace />;
  return children;
}
