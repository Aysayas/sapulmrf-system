import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ApiError } from '../../api/client';
import { TYPE_LABEL, useDevices, useNewDeviceKey, useRegisterDevice, useUpdateDevice } from '../../api/devices';
import { Badge, btn, Drawer, inputCls, Toast } from '../../components/ui';
const when = (iso) => iso ? new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' }) : 'Never';
const STATUS = {
    online: _jsx(Badge, { kind: "ok", children: "\u25CF Online" }),
    offline: _jsx(Badge, { kind: "crit", children: "\u25CB Offline" }),
    never: _jsx(Badge, { kind: "dash", children: "Never connected" }),
};
export default function DevicesPage() {
    const devices = useDevices();
    const [editing, setEditing] = useState(null);
    const [shownKey, setShownKey] = useState(null);
    const [toast, setToast] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "flex items-center", children: [_jsx("p", { className: "text-sm text-ink-2", children: "Status refreshes every 30 seconds. A device is online if it checked in within the last 2 minutes." }), _jsx("button", { className: `${btn.base} ${btn.primary} ml-auto`, onClick: () => setEditing('new'), children: "+ Register device" })] }), _jsx("div", { className: "overflow-hidden rounded-xl border border-line bg-white", children: _jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsx("tr", { className: "border-b border-line text-left text-xs text-muted", children: ['Device ID', 'Type', 'Location', 'Status', 'Last seen', ''].map((h) => (_jsx("th", { className: "px-3 py-2 font-semibold", children: h }, h))) }) }), _jsxs("tbody", { children: [devices.isPending && _jsx("tr", { children: _jsx("td", { colSpan: 6, className: "px-3 py-4 text-muted", children: "Loading\u2026" }) }), devices.isError && _jsx("tr", { children: _jsx("td", { colSpan: 6, className: "px-3 py-4 text-crit", children: devices.error.message }) }), devices.data?.length === 0 && (_jsx("tr", { children: _jsx("td", { colSpan: 6, className: "px-3 py-4 text-ink-2", children: "No devices yet. Register the weighing station, the compost sensors and the sorting camera." }) })), devices.data?.map((d) => (_jsxs("tr", { className: `border-b border-line/60 last:border-0 ${d.active ? '' : 'text-muted'}`, children: [_jsx("td", { className: "px-3 py-2.5 font-semibold", children: d.code }), _jsx("td", { className: "px-3 py-2.5", children: TYPE_LABEL[d.type] }), _jsx("td", { className: "px-3 py-2.5", children: d.location || '—' }), _jsx("td", { className: "px-3 py-2.5", children: d.active ? STATUS[d.status] : _jsx(Badge, { kind: "dash", children: "Deactivated" }) }), _jsx("td", { className: "px-3 py-2.5 text-ink-2", children: when(d.last_seen_at) }), _jsx("td", { className: "px-3 py-2.5 text-right", children: _jsx("button", { className: `${btn.base} ${btn.secondary} ${btn.small}`, "aria-label": `Edit ${d.code}`, onClick: () => setEditing(d), children: "Edit" }) })] }, d.id)))] })] }) }), editing && (_jsx(DeviceDrawer, { device: editing === 'new' ? null : editing, onClose: () => setEditing(null), onSaved: (msg) => {
                    setEditing(null);
                    setToast(msg);
                }, onKey: (d) => {
                    setEditing(null);
                    setShownKey(d);
                } })), shownKey && _jsx(KeyPanel, { device: shownKey, onClose: () => setShownKey(null) }), _jsx(Toast, { message: toast })] }));
}
const schema = z.object({
    code: z.string().trim().regex(/^[A-Za-z0-9-]{2,20}$/, '2–20 letters, numbers or dashes, like WS-01.'),
    type: z.enum(['weighing_station', 'compost_sensor', 'sorting_camera']),
    location: z.string().trim().max(80),
    active: z.boolean(),
});
function DeviceDrawer({ device, onClose, onSaved, onKey }) {
    const registerDevice = useRegisterDevice();
    const update = useUpdateDevice();
    const newKey = useNewDeviceKey();
    const [confirmKey, setConfirmKey] = useState(false);
    const busy = registerDevice.isPending || update.isPending || newKey.isPending;
    const error = registerDevice.error ?? update.error ?? newKey.error;
    const { register, handleSubmit, formState, setError } = useForm({
        resolver: zodResolver(schema),
        defaultValues: { code: device?.code ?? '', type: device?.type ?? 'compost_sensor', location: device?.location ?? '', active: device?.active ?? true },
    });
    const on409 = (e) => e instanceof ApiError && e.status === 409 && setError('code', { message: e.message });
    const onSubmit = (f) => device
        ? update.mutate({ id: device.id, ...f }, { onSuccess: (d) => onSaved(`${d.code} saved`), onError: on409 })
        : registerDevice.mutate({ code: f.code, type: f.type, location: f.location }, { onSuccess: onKey, onError: on409 });
    return (_jsxs(Drawer, { title: device ? `Edit ${device.code}` : 'Register device', onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary}`, onClick: onClose, children: "Cancel" }), _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: busy, onClick: handleSubmit(onSubmit), children: device ? 'Save changes' : 'Register' })] }), children: [error && !(error instanceof ApiError && error.status === 409) && (_jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit", children: error.message })), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Device type", _jsx("select", { ...register('type'), className: inputCls, children: Object.entries(TYPE_LABEL).map(([v, l]) => (_jsx("option", { value: v, children: l }, v))) })] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Device ID", _jsx("input", { ...register('code'), placeholder: "e.g. CS-03", className: `${inputCls} uppercase`, "aria-invalid": !!formState.errors.code }), formState.errors.code && _jsx("span", { className: "text-xs text-crit", children: formState.errors.code.message })] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Location", _jsx("input", { ...register('location'), placeholder: "e.g. Intake area, Sorting area, Compost bay 2", className: inputCls })] }), !device && _jsx("p", { className: "text-sm text-ink-2", children: "After you register, the device key is shown once. Copy it into the device so it can check in." }), device && (_jsxs(_Fragment, { children: [_jsxs("label", { className: "flex items-center gap-2 text-sm", children: [_jsx("input", { type: "checkbox", ...register('active'), className: "accent-leaf-700" }), "Active ", _jsx("span", { className: "text-xs text-muted", children: "A deactivated device can\u2019t check in." })] }), _jsxs("div", { className: "rounded-lg border border-line p-3 text-sm", children: [_jsx("b", { children: "Device key" }), _jsx("p", { className: "mt-1 text-ink-2", children: "Lost the key, or think someone else has it? A new key stops the old one working right away." }), !confirmKey ? (_jsx("button", { className: `${btn.base} ${btn.secondary} ${btn.small} mt-2`, onClick: () => setConfirmKey(true), children: "Generate new key" })) : (_jsxs("div", { className: "mt-2 flex items-center gap-2", children: [_jsx("span", { className: "text-xs font-semibold text-warn", children: "The device stops connecting until you update it." }), _jsx("button", { className: `${btn.base} ${btn.primary} ${btn.small}`, disabled: busy, onClick: () => newKey.mutate(device.id, { onSuccess: onKey }), children: "Yes, generate" })] }))] })] }))] }));
}
function KeyPanel({ device, onClose }) {
    const [copied, setCopied] = useState(false);
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "fixed inset-0 z-20 bg-leaf-900/35" }), _jsxs("div", { role: "dialog", "aria-modal": "true", "aria-label": `Key for ${device.code}`, className: "fixed top-1/2 left-1/2 z-20 flex w-[520px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-2xl bg-white p-6 shadow-2xl", children: [_jsxs("h2", { className: "text-lg font-bold", children: ["Key for ", device.code] }), _jsxs("p", { className: "text-sm text-ink-2", children: ["Put this key in the device\u2019s settings. It sends it in the ", _jsx("code", { children: "X-Device-Key" }), " header when it checks in."] }), _jsx("code", { "aria-label": "Device key", className: "rounded-lg bg-surface-2 px-3 py-2 font-mono text-sm break-all", children: device.key }), _jsx("p", { className: "rounded-lg bg-warn-100 px-3 py-2 text-sm font-semibold text-warn", children: "You won\u2019t see this key again. Copy it now." }), _jsxs("div", { className: "flex justify-end gap-2", children: [_jsx("button", { className: `${btn.base} ${btn.secondary}`, onClick: () => navigator.clipboard.writeText(device.key).then(() => setCopied(true)), children: copied ? 'Copied ✓' : 'Copy key' }), _jsx("button", { className: `${btn.base} ${btn.primary}`, onClick: onClose, children: "Done" })] })] })] }));
}
