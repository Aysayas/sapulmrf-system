import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { useAccess, useSaveAccess } from '../../api/access';
import { btn, Toast } from '../../components/ui';
const ROLES = [
    ['Barangay Administrator', 'Manages accounts, settings and approvals. Fixed.'],
    ['MRF Operator', 'Records the daily MRF work. Fixed.'],
    ['Authorized Barangay Staff', 'View only. The screens below are turned on per person.'],
];
export default function RolesPage() {
    const access = useAccess();
    const save = useSaveAccess();
    const [edits, setEdits] = useState({});
    const [toast, setToast] = useState(null);
    const changed = useMemo(() => Object.entries(edits).filter(([, g]) => Object.keys(g).length), [edits]);
    const isOn = (userId, s) => edits[userId]?.[s] ?? access.data.staff.find((p) => p.user_id === userId).grants[s];
    const toggle = (userId, s) => {
        const original = access.data.staff.find((p) => p.user_id === userId).grants[s];
        const next = !isOn(userId, s);
        setEdits((e) => {
            const g = { ...e[userId] };
            if (next === original)
                delete g[s];
            else
                g[s] = next;
            return { ...e, [userId]: g };
        });
    };
    const onSave = () => save.mutate(changed.map(([id, grants]) => ({ userId: Number(id), grants })), {
        onSuccess: () => {
            setEdits({});
            setToast('Staff access saved');
        },
    });
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "grid grid-cols-3 gap-4", children: ROLES.map(([name, desc]) => (_jsxs("div", { className: "rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "text-sm font-bold", children: name }), _jsx("p", { className: "mt-1 text-xs text-ink-2", children: desc })] }, name))) }), _jsxs("div", { className: "rounded-xl border border-line bg-white p-4", children: [_jsx("h3", { className: "mb-3 text-sm font-bold", children: "Staff access, per person" }), access.isPending && _jsx("p", { className: "text-muted", children: "Loading\u2026" }), access.isError && _jsx("p", { className: "text-crit", children: access.error.message }), access.data && access.data.staff.length === 0 && (_jsx("p", { className: "text-ink-2", children: "No staff accounts yet. Add one in Settings \u203A Users with the role Authorized Barangay Staff." })), access.data && access.data.staff.length > 0 && (_jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-line text-left text-xs text-muted", children: [_jsx("th", { className: "px-3 py-2 font-semibold", children: "Screen" }), access.data.staff.map((p) => (_jsxs("th", { className: "px-3 py-2 text-center font-semibold", children: [p.name, !p.active && _jsx("span", { className: "block font-normal", children: "(disabled)" })] }, p.user_id)))] }) }), _jsx("tbody", { children: access.data.screens.map((s) => (_jsxs("tr", { className: "border-b border-line/60 last:border-0", children: [_jsx("td", { className: "px-3 py-2.5", children: s.label }), access.data.staff.map((p) => (_jsx("td", { className: "px-3 py-2.5 text-center", children: _jsx("input", { type: "checkbox", className: "size-4 accent-leaf-700", "aria-label": `${s.label} for ${p.name}`, checked: isOn(p.user_id, s.key), onChange: () => toggle(p.user_id, s.key) }) }, p.user_id)))] }, s.key))) })] }))] }), save.error && _jsx("p", { role: "alert", className: "text-sm font-semibold text-crit", children: save.error.message }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: !changed.length || save.isPending, onClick: onSave, children: "Save access" }), changed.length > 0 && _jsxs("span", { className: "text-sm text-ink-2", children: ["Unsaved changes for ", changed.length, " person", changed.length > 1 ? 's' : ''] })] }), _jsx(Toast, { message: toast })] }));
}
