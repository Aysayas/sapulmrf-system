import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { useItems } from '../../api/masterdata';
import { useRanges, useSaveRanges } from '../../api/settings';
import { btn, inputCls, Toast } from '../../components/ui';
const num = (label, min, max) => z.number({ error: `Enter ${label}.` }).min(min, `At least ${min}.`).max(max, `At most ${max}.`);
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
export default function RangesPage() {
    const ranges = useRanges();
    const areas = useItems('storage-areas');
    if (ranges.isPending || areas.isPending)
        return _jsx("p", { className: "text-muted", children: "Loading\u2026" });
    if (ranges.isError || areas.isError)
        return _jsx("p", { className: "text-crit", children: (ranges.error ?? areas.error).message });
    return _jsx(RangesForm, { ranges: ranges.data, areas: areas.data.filter((a) => a.active) });
}
function RangesForm({ ranges, areas }) {
    const save = useSaveRanges();
    const [toast, setToast] = useState(null);
    const { register, control, handleSubmit, formState } = useForm({
        resolver: zodResolver(schema),
        defaultValues: { ...ranges, storage_areas: areas.map((a) => ({ id: a.id, name: a.name, capacity_kg: a.capacity_kg, alert_pct: a.alert_pct })) },
    });
    const rows = useFieldArray({ control, name: 'storage_areas' });
    const e = formState.errors;
    const field = (name, label, unit, step = 'any') => (_jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: [label, _jsxs("span", { className: "flex items-center gap-2", children: [_jsx("input", { type: "number", step: step, ...register(name, { valueAsNumber: true }), className: inputCls, "aria-invalid": !!e[name] }), _jsx("span", { className: "font-normal text-muted", children: unit })] }), e[name] && _jsx("span", { className: "text-xs font-normal text-crit", children: e[name]?.message })] }));
    const onSubmit = (f) => save.mutate({ ...f, storage_areas: f.storage_areas.map(({ id, capacity_kg, alert_pct }) => ({ id, capacity_kg, alert_pct })) }, { onSuccess: () => setToast('Ranges saved') });
    return (_jsxs("form", { noValidate: true, onSubmit: handleSubmit(onSubmit), className: "flex flex-col gap-4", children: [_jsxs("div", { className: "grid grid-cols-3 gap-4", children: [_jsxs("section", { "aria-label": "Compost temperature", className: "rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "mb-3 text-sm font-bold", children: "Compost temperature" }), _jsxs("div", { className: "grid grid-cols-2 gap-3", children: [field('compost_temp_min', 'Minimum', '°C'), field('compost_temp_max', 'Maximum', '°C')] })] }), _jsxs("section", { "aria-label": "Compost moisture", className: "rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "mb-3 text-sm font-bold", children: "Compost moisture" }), _jsxs("div", { className: "grid grid-cols-2 gap-3", children: [field('moisture_min', 'Minimum', '%'), field('moisture_max', 'Maximum', '%')] })] }), _jsxs("section", { "aria-label": "Predictions", className: "rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "mb-3 text-sm font-bold", children: "Predictions" }), _jsxs("div", { className: "flex flex-col gap-3", children: [field('prediction_min_days', 'Days of records before showing predictions', 'days', '1'), field('anomaly_sd', 'Flag weights more than', 'standard deviations', '0.1')] })] })] }), _jsxs("section", { "aria-label": "Storage capacity limits", className: "rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "mb-3 text-sm font-bold", children: "Storage capacity limits" }), rows.fields.length === 0 ? (_jsx("p", { className: "text-sm text-ink-2", children: "No storage areas yet. Add them in Settings \u203A Master data." })) : (_jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-line text-left text-xs text-muted", children: [_jsx("th", { className: "px-3 py-2 font-semibold", children: "Area" }), _jsx("th", { className: "px-3 py-2 font-semibold", children: "Capacity (kg)" }), _jsx("th", { className: "px-3 py-2 font-semibold", children: "Alert when this full (%)" })] }) }), _jsx("tbody", { children: rows.fields.map((r, i) => (_jsxs("tr", { className: "border-b border-line/60 last:border-0", children: [_jsx("td", { className: "px-3 py-2 font-semibold", children: r.name }), _jsxs("td", { className: "px-3 py-2", children: [_jsx("input", { type: "number", "aria-label": `Capacity for ${r.name}`, ...register(`storage_areas.${i}.capacity_kg`, { valueAsNumber: true }), className: `${inputCls} w-36` }), e.storage_areas?.[i]?.capacity_kg && _jsx("span", { className: "block text-xs text-crit", children: e.storage_areas[i]?.capacity_kg?.message })] }), _jsxs("td", { className: "px-3 py-2", children: [_jsx("input", { type: "number", "aria-label": `Alert level for ${r.name}`, ...register(`storage_areas.${i}.alert_pct`, { valueAsNumber: true }), className: `${inputCls} w-28` }), e.storage_areas?.[i]?.alert_pct && _jsx("span", { className: "block text-xs text-crit", children: e.storage_areas[i]?.alert_pct?.message })] })] }, r.id))) })] }))] }), save.error && _jsx("p", { role: "alert", className: "text-sm font-semibold text-crit", children: save.error.message }), _jsx("div", { children: _jsx("button", { type: "submit", className: `${btn.base} ${btn.primary}`, disabled: save.isPending, children: "Save ranges" }) }), _jsx(Toast, { message: toast })] }));
}
