import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useNavigate } from 'react-router';
import { z } from 'zod';
import { HOME, useLogin, useMe } from '../../api/auth';

const BALES = '/login-bales.jpg'; // Unsplash photo, kept in public/ so the login page works offline

const schema = z.object({
  username: z.string().trim().min(1, 'Enter your username.'),
  password: z.string().min(1, 'Enter your password.'),
});
type Form = z.infer<typeof schema>;

export default function LoginPage() {
  const me = useMe();
  const login = useLogin();
  const navigate = useNavigate();
  const [showPw, setShowPw] = useState(false);
  const [api, setApi] = useState('checking…');
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) });

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((b: { status: string; db: string }) => setApi(b.status === 'ok' ? 'ok' : `database ${b.db}`))
      .catch(() => setApi('unreachable'));
  }, []);

  if (me.data) return <Navigate to={HOME[me.data.role]} replace />;

  const onSubmit = (f: Form) => login.mutate(f, { onSuccess: (u) => navigate(HOME[u.role], { replace: true }) });
  const field = 'rounded-lg border border-edge px-3 py-2 font-normal outline-leaf-700';

  return (
    <main
      className="grid min-h-screen place-items-center bg-cover bg-center p-4"
      style={{ backgroundImage: `linear-gradient(rgba(15,59,42,.78),rgba(15,59,42,.62)), url(${BALES})` }}
    >
      <form noValidate className="flex w-full max-w-sm flex-col gap-4 rounded-2xl bg-white p-8 shadow-2xl" onSubmit={handleSubmit(onSubmit)}>
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-lg bg-leaf-700 text-xs font-bold text-white">MRF</span>
          <div>
            <div className="font-bold">SapulMRF</div>
            <div className="text-xs text-muted">Barangay Sapul, Calapan City</div>
          </div>
        </div>
        <h1 className="text-xl font-extrabold">Log in</h1>
        {login.error && (
          <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit shadow-[inset_4px_0_0_var(--color-crit)]">
            {login.error.message}
          </p>
        )}
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Username
          <input {...register('username')} autoComplete="username" className={field} aria-invalid={!!formState.errors.username} />
          {formState.errors.username && <span className="text-xs text-crit">{formState.errors.username.message}</span>}
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Password
          <input
            {...register('password')}
            type={showPw ? 'text' : 'password'}
            autoComplete="current-password"
            className={field}
            aria-invalid={!!formState.errors.password}
          />
          {formState.errors.password && <span className="text-xs text-crit">{formState.errors.password.message}</span>}
        </label>
        <div className="flex items-center justify-between gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={showPw} onChange={(e) => setShowPw(e.target.checked)} className="accent-leaf-700" />
            Show password
          </label>
          <span className="text-right text-muted">Forgot it? Ask the administrator</span>
        </div>
        <button type="submit" disabled={login.isPending} className="rounded-lg bg-leaf-700 py-2.5 font-semibold text-white hover:bg-leaf-800 disabled:opacity-60">
          {login.isPending ? 'Logging in…' : 'Log in'}
        </button>
        <p className="text-xs text-muted">Only authorized barangay accounts can log in.</p>
        <p className="border-t border-line pt-3 text-xs text-muted" aria-live="polite">
          API: <span className={api === 'ok' ? 'font-semibold text-leaf-700' : 'font-semibold text-crit'}>{api}</span>
        </p>
      </form>
    </main>
  );
}
