import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { useItems, type Item } from '../../api/masterdata';
import { useRanges, useSaveRanges, type Ranges } from '../../api/settings';
import { btn, inputCls, Toast } from '../../components/ui';

const num = (label: string, min: number, max: number) =>
  z.number({ error: `Enter ${label}.` }).min(min, `At least ${min}.`).max(max, `At most ${max}.`);

const schema = z
  .object({
    compost_temp_min: num('a temperature', -10, 100),
    compost_temp_max: num('a temperature', -10, 100),
    moisture_min: num('a moisture level', 0, 100),
    moisture_max: num('a moisture level', 0, 100),
    prediction_min_days: num('a number of days', 1, 365).int('Whole days only.'),
    anomaly_sd: num('a number', 1, 5),
    storage_areas: z.array(z.object({ id: z.number(), name: z.string(), capacity_kg: num('a capacity', 1, 1_000_000).int(), alert_pct: num('a percentage', 1, 100).int() })),
  })
  .refine((f) => f.compost_temp_min < f.compost_temp_max, { path: ['compost_temp_max'], message: 'Must be higher than the minimum.' })
  .refine((f) => f.moisture_min < f.moisture_max, { path: ['moisture_max'], message: 'Must be higher than the minimum.' });
type Form = z.infer<typeof schema>;

export default function RangesPage() {
  const ranges = useRanges();
  const areas = useItems('storage-areas');
  if (ranges.isPending || areas.isPending) return <p className="text-muted">Loading…</p>;
  if (ranges.isError || areas.isError) return <p className="text-crit">{(ranges.error ?? areas.error)!.message}</p>;
  return <RangesForm ranges={ranges.data} areas={areas.data.filter((a) => a.active)} />;
}

function RangesForm({ ranges, areas }: { ranges: Ranges; areas: Item[] }) {
  const save = useSaveRanges();
  const [toast, setToast] = useState<string | null>(null);
  const { register, control, handleSubmit, formState } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { ...ranges, storage_areas: areas.map((a) => ({ id: a.id, name: a.name, capacity_kg: a.capacity_kg!, alert_pct: a.alert_pct! })) },
  });
  const rows = useFieldArray({ control, name: 'storage_areas' });
  const e = formState.errors;
  const field = (name: keyof Ranges, label: string, unit: string, step = 'any') => (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {label}
      <span className="flex items-center gap-2">
        <input type="number" step={step} {...register(name, { valueAsNumber: true })} className={inputCls} aria-invalid={!!e[name]} />
        <span className="font-normal text-muted">{unit}</span>
      </span>
      {e[name] && <span className="text-xs font-normal text-crit">{e[name]?.message}</span>}
    </label>
  );

  const onSubmit = (f: Form) =>
    save.mutate(
      { ...f, storage_areas: f.storage_areas.map(({ id, capacity_kg, alert_pct }) => ({ id, capacity_kg, alert_pct })) },
      { onSuccess: () => setToast('Ranges saved') },
    );

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-4">
        <section className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-3 text-sm font-bold">Compost temperature</h3>
          <div className="grid grid-cols-2 gap-3">
            {field('compost_temp_min', 'Minimum', '°C')}
            {field('compost_temp_max', 'Maximum', '°C')}
          </div>
        </section>
        <section className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-3 text-sm font-bold">Compost moisture</h3>
          <div className="grid grid-cols-2 gap-3">
            {field('moisture_min', 'Minimum', '%')}
            {field('moisture_max', 'Maximum', '%')}
          </div>
        </section>
        <section className="rounded-xl border border-line bg-white p-4">
          <h3 className="mb-3 text-sm font-bold">Predictions</h3>
          <div className="flex flex-col gap-3">
            {field('prediction_min_days', 'Days of records before showing predictions', 'days', '1')}
            {field('anomaly_sd', 'Flag weights more than', 'standard deviations', '0.1')}
          </div>
        </section>
      </div>
      <section className="rounded-xl border border-line bg-white p-4">
        <h3 className="mb-3 text-sm font-bold">Storage capacity limits</h3>
        {rows.fields.length === 0 ? (
          <p className="text-sm text-ink-2">No storage areas yet. Add them in Settings › Master data.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="px-3 py-2 font-semibold">Area</th>
                <th className="px-3 py-2 font-semibold">Capacity (kg)</th>
                <th className="px-3 py-2 font-semibold">Alert when this full (%)</th>
              </tr>
            </thead>
            <tbody>
              {rows.fields.map((r, i) => (
                <tr key={r.id} className="border-b border-line/60 last:border-0">
                  <td className="px-3 py-2 font-semibold">{r.name}</td>
                  <td className="px-3 py-2">
                    <input type="number" aria-label={`Capacity for ${r.name}`} {...register(`storage_areas.${i}.capacity_kg`, { valueAsNumber: true })} className={`${inputCls} w-36`} />
                    {e.storage_areas?.[i]?.capacity_kg && <span className="block text-xs text-crit">{e.storage_areas[i]?.capacity_kg?.message}</span>}
                  </td>
                  <td className="px-3 py-2">
                    <input type="number" aria-label={`Alert level for ${r.name}`} {...register(`storage_areas.${i}.alert_pct`, { valueAsNumber: true })} className={`${inputCls} w-28`} />
                    {e.storage_areas?.[i]?.alert_pct && <span className="block text-xs text-crit">{e.storage_areas[i]?.alert_pct?.message}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {save.error && <p role="alert" className="text-sm font-semibold text-crit">{save.error.message}</p>}
      <div>
        <button type="submit" className={`${btn.base} ${btn.primary}`} disabled={save.isPending}>
          Save ranges
        </button>
      </div>
      <Toast message={toast} />
    </form>
  );
}
