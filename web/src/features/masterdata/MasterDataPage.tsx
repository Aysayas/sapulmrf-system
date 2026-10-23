import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ApiError } from '../../api/client';
import { useItems, useSaveItem, type Item, type Kind } from '../../api/masterdata';
import { btn, Drawer, inputCls, Toast } from '../../components/ui';

const CARDS: { kind: Kind; title: string; noun: string; empty: string }[] = [
  { kind: 'categories', title: 'Waste categories', noun: 'waste category', empty: '' },
  { kind: 'puroks', title: 'Source areas', noun: 'source area', empty: 'Add each purok that delivers to the MRF.' },
  { kind: 'materials', title: 'Recyclable materials', noun: 'material', empty: '' },
  { kind: 'storage-areas', title: 'Storage areas', noun: 'storage area', empty: 'Add each storage area with its capacity.' },
];

export default function MasterDataPage() {
  const [editing, setEditing] = useState<{ kind: Kind; item: Item | null } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  return (
    <>
      <div className="grid grid-cols-4 gap-4">
        {CARDS.map((c) => (
          <ItemCard key={c.kind} {...c} onEdit={(item) => setEditing({ kind: c.kind, item })} />
        ))}
      </div>
      {editing && (
        <ItemDrawer
          {...editing}
          noun={CARDS.find((c) => c.kind === editing.kind)!.noun}
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

function ItemCard({ kind, title, empty, onEdit }: { kind: Kind; title: string; empty: string; onEdit: (item: Item | null) => void }) {
  const items = useItems(kind);
  return (
    <section aria-label={title} className="flex flex-col rounded-xl border border-line bg-white p-4">
      <h3 className="mb-2 text-sm font-bold">{title}</h3>
      {items.isPending && <p className="text-sm text-muted">Loading…</p>}
      {items.isError && <p className="text-sm text-crit">{items.error.message}</p>}
      {items.data?.length === 0 && <p className="text-sm text-ink-2">{empty || 'Nothing yet.'}</p>}
      <ul>
        {items.data?.map((i) => (
          <li key={i.id} className={`flex items-center gap-2 border-b border-line/60 py-2 text-sm last:border-0 ${i.active ? '' : 'text-muted'}`}>
            <span className="min-w-0 flex-1">
              {i.name}
              {i.capacity_kg != null && <span className="block text-xs text-ink-2">{i.capacity_kg.toLocaleString()} kg · alert at {i.alert_pct}%</span>}
              {!i.active && <span className="block text-xs">Inactive</span>}
            </span>
            <button className={`${btn.base} ${btn.secondary} ${btn.small}`} aria-label={`Edit ${i.name}`} onClick={() => onEdit(i)}>
              Edit
            </button>
          </li>
        ))}
      </ul>
      <button className={`${btn.base} ${btn.secondary} ${btn.small} mt-3 self-start`} onClick={() => onEdit(null)}>
        + Add
      </button>
    </section>
  );
}

const schema = z.object({
  name: z.string().trim().min(1, 'Enter a name.').max(80),
  active: z.boolean(),
  capacity_kg: z.number({ error: 'Enter the capacity in kg.' }).int().min(1, 'At least 1 kg.').optional(),
  alert_pct: z.number({ error: 'Enter a percentage.' }).int().min(1).max(100, 'At most 100%.').optional(),
});
type Form = z.infer<typeof schema>;

function ItemDrawer({ kind, item, noun, onClose, onSaved }: { kind: Kind; item: Item | null; noun: string; onClose: () => void; onSaved: (m: string) => void }) {
  const save = useSaveItem(kind);
  const isArea = kind === 'storage-areas';
  const { register, handleSubmit, formState, setError } = useForm<Form>({
    resolver: zodResolver(isArea ? schema.required({ capacity_kg: true, alert_pct: true }) : schema),
    defaultValues: { name: item?.name ?? '', active: item?.active ?? true, capacity_kg: item?.capacity_kg ?? undefined, alert_pct: item?.alert_pct ?? 90 },
  });
  const err = (k: keyof Form) => formState.errors[k] && <span className="text-xs text-crit">{formState.errors[k]?.message}</span>;
  const onSubmit = (f: Form) =>
    save.mutate(
      { id: item?.id, name: f.name, ...(item ? { active: f.active } : {}), ...(isArea ? { capacity_kg: f.capacity_kg, alert_pct: f.alert_pct } : {}) },
      {
        onSuccess: (saved) => onSaved(item ? `${saved.name} saved` : `${saved.name} added`),
        onError: (e) => e instanceof ApiError && e.status === 409 && setError('name', { message: e.message }),
      },
    );

  return (
    <Drawer
      title={item ? `Edit ${item.name}` : `Add ${noun}`}
      onClose={onClose}
      footer={
        <>
          <button className={`${btn.base} ${btn.secondary}`} onClick={onClose}>Cancel</button>
          <button className={`${btn.base} ${btn.primary}`} disabled={save.isPending} onClick={handleSubmit(onSubmit)}>
            {item ? 'Save changes' : `Add ${noun}`}
          </button>
        </>
      }
    >
      {save.error && !(save.error instanceof ApiError && save.error.status === 409) && (
        <p role="alert" className="rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit">{save.error.message}</p>
      )}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Name
        <input {...register('name')} className={inputCls} aria-invalid={!!formState.errors.name} />
        {err('name')}
      </label>
      {isArea && (
        <>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Capacity (kg)
            <input {...register('capacity_kg', { valueAsNumber: true })} type="number" min={1} className={inputCls} aria-invalid={!!formState.errors.capacity_kg} />
            {err('capacity_kg')}
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Alert when this full (%)
            <input {...register('alert_pct', { valueAsNumber: true })} type="number" min={1} max={100} className={inputCls} aria-invalid={!!formState.errors.alert_pct} />
            {err('alert_pct')}
            <span className="text-xs font-normal text-muted">An alert is raised when stock reaches this share of the capacity.</span>
          </label>
        </>
      )}
      {item && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register('active')} className="accent-leaf-700" />
          Active
          <span className="text-xs text-muted">Inactive items leave the pick lists but keep their history.</span>
        </label>
      )}
    </Drawer>
  );
}
