import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ApiError } from '../../api/client';
import { useItems, useSaveItem } from '../../api/masterdata';
import { btn, Drawer, inputCls, Toast } from '../../components/ui';
const CARDS = [
    { kind: 'categories', title: 'Waste categories', noun: 'waste category', empty: '' },
    { kind: 'puroks', title: 'Source areas', noun: 'source area', empty: 'Add each purok that delivers to the MRF.' },
    { kind: 'materials', title: 'Recyclable materials', noun: 'material', empty: '' },
    { kind: 'storage-areas', title: 'Storage areas', noun: 'storage area', empty: 'Add each storage area with its capacity.' },
];
export default function MasterDataPage() {
    const [editing, setEditing] = useState(null);
    const [toast, setToast] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "grid grid-cols-4 gap-4", children: CARDS.map((c) => (_jsx(ItemCard, { ...c, onEdit: (item) => setEditing({ kind: c.kind, item }) }, c.kind))) }), editing && (_jsx(ItemDrawer, { ...editing, noun: CARDS.find((c) => c.kind === editing.kind).noun, onClose: () => setEditing(null), onSaved: (msg) => {
                    setEditing(null);
                    setToast(msg);
                } })), _jsx(Toast, { message: toast })] }));
}
function ItemCard({ kind, title, empty, onEdit }) {
    const items = useItems(kind);
    return (_jsxs("section", { "aria-label": title, className: "flex flex-col rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "mb-2 text-sm font-bold", children: title }), items.isPending && _jsx("p", { className: "text-sm text-muted", children: "Loading\u2026" }), items.isError && _jsx("p", { className: "text-sm text-crit", children: items.error.message }), items.data?.length === 0 && _jsx("p", { className: "text-sm text-ink-2", children: empty || 'Nothing yet.' }), _jsx("ul", { children: items.data?.map((i) => (_jsxs("li", { className: `flex items-center gap-2 border-b border-line/60 py-2 text-sm last:border-0 ${i.active ? '' : 'text-muted'}`, children: [_jsxs("span", { className: "min-w-0 flex-1", children: [i.name, i.capacity_kg != null && _jsxs("span", { className: "block text-xs text-ink-2", children: [i.capacity_kg.toLocaleString(), " kg \u00B7 alert at ", i.alert_pct, "%"] }), !i.active && _jsx("span", { className: "block text-xs", children: "Inactive" })] }), _jsx("button", { className: `${btn.base} ${btn.secondary} ${btn.small}`, "aria-label": `Edit ${i.name}`, onClick: () => onEdit(i), children: "Edit" })] }, i.id))) }), _jsx("button", { className: `${btn.base} ${btn.secondary} ${btn.small} mt-3 self-start`, onClick: () => onEdit(null), children: "+ Add" })] }));
}
const schema = z.object({
    name: z.string().trim().min(1, 'Enter a name.').max(80),
    active: z.boolean(),
    capacity_kg: z.number({ error: 'Enter the capacity in kg.' }).int().min(1, 'At least 1 kg.').optional(),
    alert_pct: z.number({ error: 'Enter a percentage.' }).int().min(1).max(100, 'At most 100%.').optional(),
});
function ItemDrawer({ kind, item, noun, onClose, onSaved }) {
    const save = useSaveItem(kind);
    const isArea = kind === 'storage-areas';
    const { register, handleSubmit, formState, setError } = useForm({
        resolver: zodResolver(isArea ? schema.required({ capacity_kg: true, alert_pct: true }) : schema),
        defaultValues: { name: item?.name ?? '', active: item?.active ?? true, capacity_kg: item?.capacity_kg ?? undefined, alert_pct: item?.alert_pct ?? 90 },
    });
    const err = (k) => formState.errors[k] && _jsx("span", { className: "text-xs text-crit", children: formState.errors[k]?.message });
    const onSubmit = (f) => save.mutate({ id: item?.id, name: f.name, ...(item ? { active: f.active } : {}), ...(isArea ? { capacity_kg: f.capacity_kg, alert_pct: f.alert_pct } : {}) }, {
        onSuccess: (saved) => onSaved(item ? `${saved.name} saved` : `${saved.name} added`),
        onError: (e) => e instanceof ApiError && e.status === 409 && setError('name', { message: e.message }),
    });
    return (_jsxs(Drawer, { title: item ? `Edit ${item.name}` : `Add ${noun}`, onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary}`, onClick: onClose, children: "Cancel" }), _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: save.isPending, onClick: handleSubmit(onSubmit), children: item ? 'Save changes' : `Add ${noun}` })] }), children: [save.error && !(save.error instanceof ApiError && save.error.status === 409) && (_jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit", children: save.error.message })), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Name", _jsx("input", { ...register('name'), className: inputCls, "aria-invalid": !!formState.errors.name }), err('name')] }), isArea && (_jsxs(_Fragment, { children: [_jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Capacity (kg)", _jsx("input", { ...register('capacity_kg', { valueAsNumber: true }), type: "number", min: 1, className: inputCls, "aria-invalid": !!formState.errors.capacity_kg }), err('capacity_kg')] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Alert when this full (%)", _jsx("input", { ...register('alert_pct', { valueAsNumber: true }), type: "number", min: 1, max: 100, className: inputCls, "aria-invalid": !!formState.errors.alert_pct }), err('alert_pct'), _jsx("span", { className: "text-xs font-normal text-muted", children: "An alert is raised when stock reaches this share of the capacity." })] })] })), item && (_jsxs("label", { className: "flex items-center gap-2 text-sm", children: [_jsx("input", { type: "checkbox", ...register('active'), className: "accent-leaf-700" }), "Active", _jsx("span", { className: "text-xs text-muted", children: "Inactive items leave the pick lists but keep their history." })] }))] }));
}
