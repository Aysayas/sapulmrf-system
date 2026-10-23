import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useMyAdjustments, useRequestAdjustment } from '../../api/approvals';
import { useItems } from '../../api/masterdata';
import { useInventory } from '../../api/operations';
import { FillBar } from '../../components/charts';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';
export default function StoragePage() {
    const inv = useInventory();
    const mine = useMyAdjustments();
    const [adjusting, setAdjusting] = useState(null);
    const [done, setDone] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Storage", sub: "What is stored where, and how full each area is." }), inv.isPending && _jsx("p", { className: "text-muted", children: "Loading\u2026" }), inv.error && _jsx("p", { className: "text-crit", children: inv.error.message }), inv.data && (_jsx("section", { "aria-label": "Storage areas", className: "rounded-xl border border-line bg-white px-3 py-2", children: inv.data.areas.map((a) => _jsx(FillBar, { area: a }, a.id)) })), _jsx("h2", { className: "text-lg font-bold", children: "Stock" }), _jsx("p", { className: "-mt-3 text-sm text-ink-2", children: "Counted something different? Tap the row to ask for an adjustment." }), _jsxs("ul", { "aria-label": "Stock", className: "flex flex-col gap-2", children: [inv.data?.stock.length === 0 && _jsx("li", { className: "text-muted", children: "Nothing in storage." }), inv.data?.stock.map((s) => (_jsx("li", { children: _jsxs("button", { className: `${touch} flex w-full items-center gap-3 rounded-xl border border-line bg-white p-3 text-left`, "aria-label": `Request adjustment for ${s.material} in ${s.area}`, onClick: () => setAdjusting(s), children: [_jsxs("span", { className: "flex-1", children: [_jsx("b", { children: s.material }), _jsxs("small", { className: "block text-ink-2", children: [s.area, " \u00B7 ", s.bags, " bags"] })] }), _jsx("span", { className: "font-bold tabular-nums", children: kg(s.kg) }), _jsx("span", { "aria-hidden": true, className: "text-muted", children: "\u203A" })] }) }, `${s.area}-${s.material}`)))] }), _jsx("h2", { className: "text-lg font-bold", children: "My requests" }), _jsxs("ul", { "aria-label": "My requests", className: "flex flex-col gap-2", children: [mine.isPending && _jsx("li", { className: "text-muted", children: "Loading\u2026" }), mine.data?.length === 0 && _jsx("li", { className: "text-muted", children: "No adjustment requests in the last 30 days." }), mine.data?.map((r) => (_jsxs(Card, { label: `${r.material} in ${r.area}`, children: [_jsxs("div", { className: "flex items-start gap-2", children: [_jsxs("b", { className: "flex-1", children: [r.material, " \u00B7 ", r.area] }), _jsx(StatusBadge, { status: r.status })] }), _jsxs("p", { className: "text-sm text-ink-2", children: [kg(r.system_kg), " \u2192 ", kg(r.actual_kg), " \u00B7 ", r.reason] }), _jsxs("p", { className: "text-xs text-muted", children: ["Sent ", when(r.requested_at), r.decided_by ? ` · ${r.status} by ${r.decided_by}` : ''] }), r.comment && _jsxs("p", { className: "mt-1 text-sm", children: ["\u201C", r.comment, "\u201D"] })] }, r.id)))] }), adjusting && (_jsx(AdjustSheet, { row: adjusting, onClose: () => setAdjusting(null), onSent: (m) => { setAdjusting(null); setDone(m); } })), _jsx(Toast, { message: done })] }));
}
const schema = z.object({
    actual_kg: z.number({ error: 'Enter the kg you counted.' }).min(0, 'Can’t be below 0.').max(50000, 'That is more than any area holds.'),
    reason: z.string().trim().min(1, 'Say why the count is different.').max(120),
    details: z.string().trim().max(200),
});
function AdjustSheet({ row, onClose, onSent }) {
    const materials = useItems('materials');
    const areas = useItems('storage-areas');
    const send = useRequestAdjustment();
    const { register, handleSubmit, formState } = useForm({ resolver: zodResolver(schema), defaultValues: { reason: '', details: '' } });
    const areaId = areas.data?.find((a) => a.name === row.area)?.id;
    const materialId = row.material === 'Residual' ? null : materials.data?.find((m) => m.name === row.material)?.id;
    const ready = areaId !== undefined && materialId !== undefined;
    const onSubmit = (f) => send.mutate({ material_id: materialId, storage_area_id: areaId, ...f }, { onSuccess: () => onSent(`Adjustment sent for approval · ${row.material}, ${row.area}`) });
    return (_jsxs(Drawer, { title: "Request inventory adjustment", onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary} ${touch}`, onClick: onClose, children: "Cancel" }), _jsx("button", { className: `${btn.base} ${btn.primary} ${touch}`, disabled: !ready || send.isPending, onClick: handleSubmit(onSubmit), children: "Send for approval" })] }), children: [send.error && _jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit", children: send.error.message }), _jsxs("div", { className: "rounded-lg bg-surface p-3 text-sm", children: [_jsx("div", { className: "text-xs text-muted", children: "Material and area" }), _jsxs("b", { children: [row.material, " \u00B7 ", row.area] }), _jsx("div", { className: "mt-2 text-xs text-muted", children: "System says" }), _jsx("b", { children: kg(row.kg) })] }), _jsx(Field, { label: "Actual count (kg)", error: formState.errors.actual_kg?.message, children: _jsx("input", { type: "number", step: "0.1", inputMode: "decimal", className: inputCls, "aria-invalid": !!formState.errors.actual_kg, ...register('actual_kg', { valueAsNumber: true }) }) }), _jsx(Field, { label: "Reason", error: formState.errors.reason?.message, children: _jsx("input", { className: inputCls, placeholder: "e.g. Wet paper removed as residual", "aria-invalid": !!formState.errors.reason, ...register('reason') }) }), _jsx(Field, { label: "Details (optional)", error: formState.errors.details?.message, children: _jsx("textarea", { rows: 3, className: inputCls, ...register('details') }) }), _jsx("p", { className: "text-sm text-ink-2", children: "Stock changes only after the Barangay Administrator approves." })] }));
}
