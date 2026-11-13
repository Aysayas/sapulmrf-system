import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useChangePassword, useKioskPin, useMe, useUpdateProfile, type User } from '../../api/auth';
import { btn, inputCls, PageHeader, Toast } from '../../components/ui';
import { Field, touch } from './shared';

export default function ProfilePage() {
  const me = useMe();
  return (
    <>
      <PageHeader title="Profile" />
      {me.isPending && <p className="text-muted">Loading…</p>}
      {me.error && <p role="alert" className="text-crit">{me.error.message}</p>}
      {me.data && <DetailsForm user={me.data} />}
      {me.data && <PasswordForm />}
      {me.data?.role === 'operator' && <KioskPinForm hasPin={me.data.has_kiosk_pin} />}
    </>
  );
}

const ServerError = ({ error }: { error: Error | null }) =>
  error && <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{error.message}</p>;

// Mirrors ProfileIn and PasswordIn on the server, which stays the authority.
const detailsSchema = z.object({
  name: z.string().trim().min(1, 'Enter your name.').max(120),
  contact: z.string().trim().max(30).regex(/^[0-9+() -]*$/, 'Use numbers and + ( ) - only.'),
});
type Details = z.infer<typeof detailsSchema>;

function DetailsForm({ user }: { user: User }) {
  const save = useUpdateProfile();
  const { register, handleSubmit, formState: { errors: e } } = useForm<Details>({
    resolver: zodResolver(detailsSchema),
    defaultValues: { name: user.name, contact: user.contact },
  });

  return (
    <form aria-label="Personal details" className="flex flex-col gap-3 rounded-xl border border-line bg-white p-3"
      onSubmit={handleSubmit((f) => save.mutate(f))}>
      <h2 className="text-lg font-bold">Personal details</h2>
      <ServerError error={save.error} />
      <Field label="Full name" error={e.name?.message}>
        <input className={`${inputCls} ${touch}`} autoComplete="name" aria-invalid={!!e.name} {...register('name')} />
      </Field>
      <Field label="Contact number" error={e.contact?.message}>
        <input type="tel" className={`${inputCls} ${touch}`} autoComplete="tel" aria-invalid={!!e.contact} {...register('contact')} />
      </Field>
      <Field label="Username">
        <input className={`${inputCls} ${touch} bg-surface`} value={user.username} readOnly />
        <span className="text-xs font-normal text-ink-2">Only the administrator can change usernames.</span>
      </Field>
      <button className={`${btn.base} ${btn.primary} ${touch}`} disabled={save.isPending}>Save changes</button>
      <Toast message={save.isSuccess ? 'Profile saved' : null} />
    </form>
  );
}

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Enter your current password.'),
  new_password: z.string().min(8, 'At least 8 characters.').max(128),
  confirm: z.string(),
}).refine((f) => f.new_password === f.confirm, { path: ['confirm'], message: 'The two passwords don’t match.' });
type Password = z.infer<typeof passwordSchema>;

function PasswordForm() {
  const change = useChangePassword();
  const { register, handleSubmit, reset, formState: { errors: e } } = useForm<Password>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '', confirm: '' },
  });

  return (
    <form aria-label="Change password" className="flex flex-col gap-3 rounded-xl border border-line bg-white p-3"
      onSubmit={handleSubmit(({ current_password, new_password }) =>
        change.mutate({ current_password, new_password }, { onSuccess: () => reset() }))}>
      <h2 className="text-lg font-bold">Change password</h2>
      <ServerError error={change.error} />
      <Field label="Current password" error={e.current_password?.message}>
        <input type="password" className={`${inputCls} ${touch}`} autoComplete="current-password" aria-invalid={!!e.current_password} {...register('current_password')} />
      </Field>
      <Field label="New password" error={e.new_password?.message}>
        <input type="password" className={`${inputCls} ${touch}`} autoComplete="new-password" aria-invalid={!!e.new_password} {...register('new_password')} />
      </Field>
      <Field label="Confirm new password" error={e.confirm?.message}>
        <input type="password" className={`${inputCls} ${touch}`} autoComplete="new-password" aria-invalid={!!e.confirm} {...register('confirm')} />
      </Field>
      <p className="text-sm text-ink-2">Changing it signs you out on other devices.</p>
      <button className={`${btn.base} ${btn.secondary} ${touch}`} disabled={change.isPending}>Change password</button>
      <Toast message={change.isSuccess ? 'Password changed' : null} />
    </form>
  );
}

// Mirrors KioskPinIn on the server.
const pinSchema = z.object({
  pin: z.string().regex(/^[0-9]{4,6}$/, '4 to 6 digits.'),
  confirm: z.string(),
}).refine((f) => f.pin === f.confirm, { path: ['confirm'], message: 'The two PINs don’t match.' });
type Pin = z.infer<typeof pinSchema>;

function KioskPinForm({ hasPin }: { hasPin: boolean }) {
  const save = useKioskPin();
  const { register, handleSubmit, reset, formState: { errors: e } } = useForm<Pin>({
    resolver: zodResolver(pinSchema),
    defaultValues: { pin: '', confirm: '' },
  });
  const pinInput = { type: 'password', inputMode: 'numeric', autoComplete: 'off', maxLength: 6, className: `${inputCls} ${touch}` } as const;

  return (
    <form aria-label="Kiosk PIN" className="flex flex-col gap-3 rounded-xl border border-line bg-white p-3"
      onSubmit={handleSubmit(({ pin }) => save.mutate(pin, { onSuccess: () => reset() }))}>
      <h2 className="text-lg font-bold">Kiosk PIN</h2>
      <p className="text-sm text-ink-2">
        {hasPin ? 'You can sign in at the kiosk: tap your name, then type your PIN.' : 'Set a PIN to sign in at the drop-off kiosk.'}
        {' '}5 wrong tries lock it for 5 minutes.
      </p>
      <ServerError error={save.error} />
      <Field label={hasPin ? 'New PIN' : 'PIN'} error={e.pin?.message}>
        <input {...pinInput} aria-invalid={!!e.pin} {...register('pin')} />
      </Field>
      <Field label="Confirm PIN" error={e.confirm?.message}>
        <input {...pinInput} aria-invalid={!!e.confirm} {...register('confirm')} />
      </Field>
      <button className={`${btn.base} ${btn.secondary} ${touch}`} disabled={save.isPending}>{hasPin ? 'Change PIN' : 'Set PIN'}</button>
      {hasPin && (
        <button type="button" className={`${btn.base} ${btn.secondary} ${touch} text-crit`} disabled={save.isPending} onClick={() => save.mutate(null)}>
          Remove PIN
        </button>
      )}
      <Toast message={save.isSuccess ? (save.variables ? 'Kiosk PIN saved' : 'Kiosk PIN removed') : null} />
    </form>
  );
}
