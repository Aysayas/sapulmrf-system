import { useEffect, useState } from 'react';

// Phase 0: the screen and the API health line. Signing in arrives in Phase 1 (ADM-01).
const BALES = 'https://images.unsplash.com/photo-1764529310915-f73129d29c22?w=1800&q=70&auto=format&fit=crop';

export default function Login() {
  const [api, setApi] = useState('checking…');
  const [showPw, setShowPw] = useState(false);

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((b: { status: string; db: string }) => setApi(b.status === 'ok' ? 'ok' : `database ${b.db}`))
      .catch(() => setApi('unreachable'));
  }, []);

  return (
    <main
      className="grid min-h-screen place-items-center bg-cover bg-center p-4"
      style={{ backgroundImage: `linear-gradient(rgba(15,59,42,.78),rgba(15,59,42,.62)), url(${BALES})` }}
    >
      <form className="flex w-full max-w-sm flex-col gap-4 rounded-2xl bg-white p-8 shadow-2xl" onSubmit={(e) => e.preventDefault()}>
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-lg bg-leaf-700 text-xs font-bold text-white">MRF</span>
          <div>
            <div className="font-bold">SapulMRF</div>
            <div className="text-xs text-muted">Barangay Sapul, Calapan City</div>
          </div>
        </div>
        <h1 className="text-xl font-extrabold">Log in</h1>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Username
          <input name="username" autoComplete="username" className="rounded-lg border border-edge px-3 py-2 font-normal outline-leaf-700" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Password
          <input
            name="password"
            type={showPw ? 'text' : 'password'}
            autoComplete="current-password"
            className="rounded-lg border border-edge px-3 py-2 font-normal outline-leaf-700"
          />
        </label>
        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={showPw} onChange={(e) => setShowPw(e.target.checked)} className="accent-leaf-700" />
            Show password
          </label>
          <span className="text-muted">Forgot password? Ask the administrator</span>
        </div>
        <button type="submit" className="rounded-lg bg-leaf-700 py-2.5 font-semibold text-white hover:bg-leaf-800">
          Log in
        </button>
        <p className="text-xs text-muted">Only authorized barangay accounts can log in.</p>
        <p className="border-t border-line pt-3 text-xs text-muted" aria-live="polite">
          API: <span className={api === 'ok' ? 'font-semibold text-leaf-700' : 'font-semibold text-crit'}>{api}</span>
        </p>
      </form>
    </main>
  );
}
