import type { ReactNode } from 'react';
import { Navigate } from 'react-router';
import { ROLE_LABEL, useLogout, useMe } from '../api/auth';

/** Only a logged-in Barangay Administrator gets past this. Operator and staff sides come later. */
export default function RequireAdmin({ children }: { children: ReactNode }) {
  const me = useMe();
  const logout = useLogout();

  if (me.isPending) return <p className="p-8 text-muted">Loading…</p>;
  if (me.isError) return <p className="p-8 text-crit">Can’t reach the server. Check that Docker is running.</p>;
  if (!me.data) return <Navigate to="/login" replace />;
  if (me.data.role !== 'admin')
    return (
      <main className="grid min-h-screen place-items-center p-4">
        <div className="max-w-md rounded-2xl bg-white p-8 text-center shadow">
          <h1 className="text-xl font-extrabold">Signed in as {ROLE_LABEL[me.data.role]}</h1>
          <p className="mt-2 text-ink-2">The screens for your role aren’t built yet. Only the administrator side is available.</p>
          <button className="mt-4 rounded-lg border border-edge px-4 py-2 font-semibold" onClick={() => logout.mutate()}>
            Log out
          </button>
        </div>
      </main>
    );
  return children;
}
