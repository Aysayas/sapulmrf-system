import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ROLE_LABEL, useMe, type User } from '../../api/auth';
import { ApiError } from '../../api/client';
import { useSaveUser, useUsers } from '../../api/users';
import { Badge, btn, Drawer, inputCls, Toast } from '../../components/ui';

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : 'Never';

export default function UsersPage() {
  const users = useUsers();
  const [editing, setEditing] = useState<User | 'new' | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  return (
    <>
      <div className="flex">
        <button className={`${btn.base} ${btn.primary} ml-auto`} onClick={() => setEditing('new')}>
          + Add user
        </button>
      </div>
      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              {['Name', 'Username', 'Role', 'Status', 'Last login', ''].map((h) => (
                <th key={h} className="px-3 py-2 font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.isPending && <tr><td colSpan={6} className="px-3 py-4 text-muted">Loading…</td></tr>}
            {users.isError && <tr><td colSpan={6} className="px-3 py-4 text-crit">{users.error.message}</td></tr>}
            {users.data?.map((u) => (
              <tr key={u.id} className="border-b border-line/60 last:border-0">
                <td className="px-3 py-2.5 font-semibold">{u.name}</td>
                <td className="px-3 py-2.5">{u.username}</td>
                <td className="px-3 py-2.5">{ROLE_LABEL[u.role]}</td>
                <td className="px-3 py-2.5">{u.active ? <Badge kind="ok">Active</Badge> : <Badge kind="dash">Disabled</Badge>}</td>
                <td className="px-3 py-2.5 text-ink-2">{when(u.last_login_at)}</td>
                <td className="px-3 py-2.5 text-right">
                  <button className={`${btn.base} ${btn.secondary} ${btn.small}`} onClick={() => setEditing(u)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <UserDrawer
          user={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(msg) => {
            setEditing(null);
            setToast(msg);
          }}
        />
      )}
      <Toast message={toast} />
    </>
  );
}

const base = {
  name: z.string().trim().min(1, 'Enter the full name.').max(120),
  username: z.string().trim().regex(/^[a-z0-9._-]{3,60}$/, '3–60 characters: lowercase letters, numbers, dot, dash or underscore.'),
  // Optional because a disabled field (your own role/active) submits as undefined; the API keeps the old value.
  role: z.enum(['admin', 'operator', 'staff']).optional(),
  active: z.boolean().optional(),
};
const createSchema = z.object({ ...base, password: z.string().min(8, 'At least 8 characters.') });
const editSchema = z.object({ ...base, password: z.union([z.literal(''), z.string().min(8, 'At least 8 characters, or leave blank.')]) });
type Form = z.infer<typeof createSchema>;

function UserDrawer({ user, onClose, onSaved }: { user: User | null; onClose: () => void; onSaved: (msg: string) => void }) {
  const me = useMe().data!;
  const save = useSaveUser();
  const isSelf = user?.id === me.id;
  const { register, handleSubmit, formState, setError } = useForm<Form>({
    resolver: zodResolver(user ? editSchema : createSchema),
    defaultValues: { name: user?.name ?? '', username: user?.username ?? '', role: user?.role ?? 'staff', active: user?.active ?? true, password: '' },
  });
  const err = (k: keyof Form) => formState.errors[k] && <span className="text-xs text-crit">{formState.errors[k]?.message}</span>;

  const onSubmit = (f: Form) => {
    const body = { ...f, password: f.password || undefined, id: user?.id };
    save.mutate(body, {
      onSuccess: (u) => onSaved(user ? `${u.name} saved` : `${u.name} can now log in`),
      onError: (e) => e instanceof ApiError && e.status === 409 && setError('username', { message: e.message }),
    });
  };

  return (
    <Drawer
      title={user ? `Edit ${user.name}` : 'Add user'}
      onClose={onClose}
      footer={
        <>
          <button className={`${btn.base} ${btn.secondary}`} onClick={onClose}>Cancel</button>
          <button className={`${btn.base} ${btn.primary}`} disabled={save.isPending} onClick={handleSubmit(onSubmit)}>
            {user ? 'Save changes' : 'Create account'}
          </button>
        </>
      }
    >
      {save.error && !(save.error instanceof ApiError && save.error.status === 409) && (
        <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{save.error.message}</p>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Full name
        <input {...register('name')} className={inputCls} aria-invalid={!!formState.errors.name} />
        {err('name')}
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Username
        <input {...register('username')} autoComplete="off" className={inputCls} aria-invalid={!!formState.errors.username} />
        {err('username')}
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Role
        <select {...register('role')} className={inputCls} disabled={isSelf}>
          {(['staff', 'operator', 'admin'] as const).map((r) => (
            <option key={r} value={r}>{ROLE_LABEL[r]}</option>
          ))}
        </select>
        <span className="text-xs font-normal text-muted">
          {isSelf ? 'You can’t change your own role.' : 'Only 3 roles: Barangay Administrator, MRF Operator, Authorized Barangay Staff.'}
        </span>
      </label>
      <label className="flex flex-col gap-1 text-sm font-semibold">
        {user ? 'New password' : 'Temporary password'}
        <input {...register('password')} type="password" autoComplete="new-password" className={inputCls} aria-invalid={!!formState.errors.password}
          placeholder={user ? 'Leave blank to keep the current password' : 'At least 8 characters'} />
        {err('password')}
        <span className="text-xs font-normal text-muted">Setting a password signs the person out everywhere.</span>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register('active')} disabled={isSelf} className="accent-leaf-700" />
        Account active {isSelf && <span className="text-xs text-muted">(you can’t disable yourself)</span>}
      </label>
    </Drawer>
  );
}
