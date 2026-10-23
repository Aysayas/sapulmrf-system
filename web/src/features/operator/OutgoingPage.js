import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { OUTGOING_TYPE, useRequestOutgoing } from '../../api/approvals';
import { useItems } from '../../api/masterdata';
import { useInventory, useOutgoing } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, peso, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';
export default function OutgoingPage() {
    const out = useOutgoing(30);
    const [adding, setAdding] = useState(false);
    const [done, setDone] = useState(null);
    const v = out.data;
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Outgoing", sub: "Recyclables sold, compost given out, and residual sent for disposal." }), _jsx("button", { className: `${btn.base} ${btn.primary} ${touch} w-full`, onClick: () => setAdding(true), children: "+ Record outgoing" }), out.isPending && _jsx("p", { className: "text-muted", children: "Loading\u2026" }), out.error && _jsx("p", { className: "text-crit", children: out.error.message }), v && (_jsxs("div", { className: "grid grid-cols-2 gap-2", children: [_jsx(Kpi, { label: "Sold this month", value: kg(v.sold_kg_month), sub: "Recyclables" }), _jsx(Kpi, { label: "Income this month", value: peso(v.income_month), sub: "Approved sales only" }), _jsx(Kpi, { label: "Compost given out", value: kg(v.compost_kg_month), sub: "This month" }), _jsx(Kpi, { label: "Residual disposed", value: kg(v.disposed_kg_month), sub: "This month" })] })), _jsx("h2", { className: "text-lg font-bold", children: "Records, last 30 days" }), _jsxs("ul", { "aria-label": "Outgoing records", className: "flex flex-col gap-2", children: [v?.records.length === 0 && _jsx("li", { className: "text-muted", children: "Nothing recorded yet." }), v?.records.map((o) => (_jsxs(Card, { label: o.code, children: [_jsxs("div", { className: "flex items-start gap-2", children: [_jsxs("b", { className: "flex-1", children: [o.code, " \u00B7 ", OUTGOING_TYPE[o.type]] }), _jsx(StatusBadge, { status: o.status })] }), _jsxs("p", { className: "text-sm text-ink-2", children: [o.material, " \u00B7 ", kg(o.kg), " \u00B7 ", o.recipient, o.total !== null && ` · ${peso(o.price_per_kg)}/kg = ${peso(o.total)}`] }), _jsxs("p", { className: "text-xs text-muted", children: [when(o.requested_at), o.requested_by ? ` · ${o.requested_by}` : ''] }), o.comment && _jsxs("p", { className: "mt-1 text-sm", children: ["\u201C", o.comment, "\u201D"] })] }, o.id)))] }), adding && _jsx(NewOutgoingSheet, { onClose: () => setAdding(false), onSent: (m) => { setAdding(false); setDone(m); } }), _jsx(Toast, { message: done })] }));
}
// Mirrors OutgoingIn on the server, which stays the authority.
const schema = z.object({
    type: z.enum(['sale', 'compost', 'disposal']),
    material_id: z.number(),
    storage_area_id: z.number(),
    kg: z.number({ error: 'Enter the kg.' }).gt(0, 'Enter the kg.').max(50000),
    recipient: z.string().trim().min(1, 'Who is it going to?').max(120),
    price_per_kg: z.number().or(z.nan()),
}).superRefine((f, ctx) => {
    if (f.type === 'sale' && !f.material_id)
        ctx.addIssue({ code: 'custom', path: ['material_id'], message: 'Pick the material.' });
    if (f.type !== 'compost' && !f.storage_area_id)
        ctx.addIssue({ code: 'custom', path: ['storage_area_id'], message: 'Pick the storage area it leaves from.' });
    if (f.type === 'sale' && !(f.price_per_kg > 0))
        ctx.addIssue({ code: 'custom', path: ['price_per_kg'], message: 'Enter the price per kg.' });
});
function NewOutgoingSheet({ onClose, onSent }) {
    const materials = useItems('materials');
    const areas = useItems('storage-areas');
    const inv = useInventory();
    const compostOnHand = useOutgoing(30).data?.compost_on_hand_kg;
    const send = useRequestOutgoing();
    const { register, handleSubmit, formState, watch } = useForm({
        resolver: zodResolver(schema),
        defaultValues: { type: 'sale', material_id: 0, storage_area_id: 0, recipient: '' },
    });
    const [type, materialId, weight, price] = watch(['type', 'material_id', 'kg', 'price_per_kg']);
    const e = formState.errors;
    // The areas holding what is going out, with how much is there.
    const material = type === 'disposal' ? 'Residual' : materials.data?.find((m) => m.id === materialId)?.name;
    const sources = (inv.data?.stock ?? []).filter((s) => s.material === material)
        .map((s) => ({ id: areas.data?.find((a) => a.name === s.area)?.id ?? 0, label: `${s.area} · ${kg(s.kg)}` }));
    const onSubmit = (f) => send.mutate({
        type: f.type,
        material_id: f.type === 'sale' ? f.material_id : null,
        storage_area_id: f.type === 'compost' ? null : f.storage_area_id,
        kg: f.kg,
        recipient: f.recipient,
        price_per_kg: f.type === 'sale' ? f.price_per_kg : null,
    }, { onSuccess: (o) => onSent(`${o.code} sent for approval · ${kg(o.kg)} ${o.material}`) });
    return (_jsxs(Drawer, { title: "Record outgoing material", onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary} ${touch}`, onClick: onClose, children: "Cancel" }), _jsx("button", { className: `${btn.base} ${btn.primary} ${touch}`, disabled: send.isPending, onClick: handleSubmit(onSubmit), children: "Send for approval" })] }), children: [send.error && _jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit", children: send.error.message }), _jsxs("fieldset", { className: "flex flex-col gap-1", children: [_jsx("legend", { className: "mb-1 text-sm font-semibold", children: "Type" }), [['sale', 'Recyclable sale'], ['compost', 'Compost'], ['disposal', 'Residual for disposal']].map(([v, label]) => (_jsxs("label", { className: `${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`, children: [_jsx("input", { type: "radio", value: v, className: "accent-leaf-700", ...register('type') }), " ", label] }, v)))] }), type === 'sale' && (_jsx(Field, { label: "Material", error: e.material_id?.message, children: _jsxs("select", { className: inputCls, "aria-invalid": !!e.material_id, ...register('material_id', { valueAsNumber: true }), children: [_jsx("option", { value: 0, children: "Pick a material" }), materials.data?.filter((m) => m.active).map((m) => _jsx("option", { value: m.id, children: m.name }, m.id))] }) })), type !== 'compost' ? (_jsx(Field, { label: "From storage", error: e.storage_area_id?.message, children: _jsxs("select", { className: inputCls, "aria-invalid": !!e.storage_area_id, ...register('storage_area_id', { valueAsNumber: true }), children: [_jsx("option", { value: 0, children: material ? 'Pick an area' : 'Pick the material first' }), sources.map((s) => _jsx("option", { value: s.id, children: s.label }, s.id))] }) })) : (_jsxs("p", { className: "rounded-lg bg-surface p-3 text-sm", children: ["Compost on hand: ", _jsx("b", { children: compostOnHand === undefined ? '…' : kg(compostOnHand) })] })), _jsx(Field, { label: type === 'sale' ? 'Buyer' : 'Recipient', error: e.recipient?.message, children: _jsx("input", { className: inputCls, "aria-invalid": !!e.recipient, placeholder: type === 'disposal' ? 'e.g. City ENRO truck' : 'e.g. Buyer A Junkshop', ...register('recipient') }) }), _jsx(Field, { label: "kg", error: e.kg?.message, children: _jsx("input", { type: "number", step: "0.1", inputMode: "decimal", className: inputCls, "aria-invalid": !!e.kg, ...register('kg', { valueAsNumber: true }) }) }), type === 'sale' && (_jsxs(_Fragment, { children: [_jsx(Field, { label: "Price per kg (\u20B1)", error: e.price_per_kg?.message, children: _jsx("input", { type: "number", step: "0.01", inputMode: "decimal", className: inputCls, "aria-invalid": !!e.price_per_kg, ...register('price_per_kg', { valueAsNumber: true }) }) }), _jsxs("p", { className: "rounded-lg bg-surface p-3 text-sm", "aria-live": "polite", children: ["Total: ", _jsx("b", { children: weight > 0 && price > 0 ? peso(Math.round(weight * price * 100) / 100) : '—' }), " ", _jsx("span", { className: "text-muted", children: "(kg \u00D7 price)" })] })] })), _jsx("p", { className: "text-sm text-ink-2", children: "Stock leaves storage only after the administrator approves." })] }));
}
