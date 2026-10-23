import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ROLE_LABEL, useMe } from '../../api/auth';
import { ApiError } from '../../api/client';
import { useSaveUser, useUsers } from '../../api/users';
import { Badge, btn, Drawer, inputCls, Toast } from '../../components/ui';
const when = (iso) => iso ? new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : 'Never';
export default function UsersPage() {
    const users = useUsers();
    const [editing, setEditing] = useState(null);
    const [toast, setToast] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx("div", { className: "flex", children: _jsx("button", { className: `${btn.base} ${btn.primary} ml-auto`, onClick: () => setEditing('new'), children: "+ Add user" }) }), _jsx("div", { className: "overflow-hidden rounded-xl border border-line bg-white", children: _jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsx("tr", { className: "border-b border-line text-left text-xs text-muted", children: ['Name', 'Username', 'Role', 'Status', 'Last login', ''].map((h) => (_jsx("th", { className: "px-3 py-2 font-semibold", children: h }, h))) }) }), _jsxs("tbody", { children: [users.isPending && _jsx("tr", { children: _jsx("td", { colSpan: 6, className: "px-3 py-4 text-muted", children: "Loading\u2026" }) }), users.isError && _jsx("tr", { children: _jsx("td", { colSpan: 6, className: "px-3 py-4 text-crit", children: users.error.message }) }), users.data?.map((u) => (_jsxs("tr", { className: "border-b border-line/60 last:border-0", children: [_jsx("td", { className: "px-3 py-2.5 font-semibold", children: u.name }), _jsx("td", { className: "px-3 py-2.5", children: u.username }), _jsx("td", { className: "px-3 py-2.5", children: ROLE_LABEL[u.role] }), _jsx("td", { className: "px-3 py-2.5", children: u.active ? _jsx(Badge, { kind: "ok", children: "Active" }) : _jsx(Badge, { kind: "dash", children: "Disabled" }) }), _jsx("td", { className: "px-3 py-2.5 text-ink-2", children: when(u.last_login_at) }), _jsx("td", { className: "px-3 py-2.5 text-right", children: _jsx("button", { className: `${btn.base} ${btn.secondary} ${btn.small}`, onClick: () => setEditing(u), children: "Edit" }) })] }, u.id)))] })] }) }), editing && (_jsx(UserDrawer, { user: editing === 'new' ? null : editing, onClose: () => setEditing(null), onSaved: (msg) => {
                    setEditing(null);
                    setToast(msg);
                } })), _jsx(Toast, { message: toast })] }));
}
const base = {
    name: z.string().trim().min(1, 'Enter the full name.').max(120),
    username: z.string().trim().toLowerCase().regex(/^[a-z0-9._-]{3,60}$/, '3–60 characters: letters, numbers, dot, dash or underscore.'),
    // Optional because a disabled field (your own role/active) submits as undefined; the API keeps the old value.
    role: z.enum(['admin', 'operator', 'staff']).optional(),
    active: z.boolean().optional(),
};
const createSchema = z.object({ ...base, password: z.string().min(8, 'At least 8 characters.') });
const editSchema = z.object({ ...base, password: z.union([z.literal(''), z.string().min(8, 'At least 8 characters, or leave blank.')]) });
function UserDrawer({ user, onClose, onSaved }) {
    const me = useMe().data;
    const save = useSaveUser();
    const isSelf = user?.id === me.id;
    const { register, handleSubmit, formState, setError } = useForm({
        resolver: zodResolver(user ? editSchema : createSchema),
        defaultValues: { name: user?.name ?? '', username: user?.username ?? '', role: user?.role ?? 'staff', active: user?.active ?? true, password: '' },
    });
    const err = (k) => formState.errors[k] && _jsx("span", { className: "text-xs text-crit", children: formState.errors[k]?.message });
    const onSubmit = (f) => {
        const body = { ...f, password: f.password || undefined, id: user?.id };
        save.mutate(body, {
            onSuccess: (u) => onSaved(user ? `${u.name} saved` : `${u.name} can now log in`),
            onError: (e) => e instanceof ApiError && e.status === 409 && setError('username', { message: e.message }),
        });
    };
    return (_jsxs(Drawer, { title: user ? `Edit ${user.name}` : 'Add user', onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary}`, onClick: onClose, children: "Cancel" }), _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: save.isPending, onClick: handleSubmit(onSubmit), children: user ? 'Save changes' : 'Create account' })] }), children: [save.error && !(save.error instanceof ApiError && save.error.status === 409) && (_jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit", children: save.error.message })), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Full name", _jsx("input", { ...register('name'), className: inputCls, "aria-invalid": !!formState.errors.name }), err('name')] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Username", _jsx("input", { ...register('username'), autoComplete: "off", className: inputCls, "aria-invalid": !!formState.errors.username }), err('username')] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Role", _jsx("select", { ...register('role'), className: inputCls, disabled: isSelf, children: ['staff', 'operator', 'admin'].map((r) => (_jsx("option", { value: r, children: ROLE_LABEL[r] }, r))) }), _jsx("span", { className: "text-xs font-normal text-muted", children: isSelf ? 'You can’t change your own role.' : 'Only 3 roles: Barangay Administrator, MRF Operator, Authorized Barangay Staff.' })] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: [user ? 'New password' : 'Temporary password', _jsx("input", { ...register('password'), type: "password", autoComplete: "new-password", className: inputCls, "aria-invalid": !!formState.errors.password, placeholder: user ? 'Leave blank to keep the current password' : 'At least 8 characters' }), err('password'), _jsx("span", { className: "text-xs font-normal text-muted", children: "Setting a password signs the person out everywhere." })] }), _jsxs("label", { className: "flex items-center gap-2 text-sm", children: [_jsx("input", { type: "checkbox", ...register('active'), disabled: isSelf, className: "accent-leaf-700" }), "Account active ", isSelf && _jsx("span", { className: "text-xs text-muted", children: "(you can\u2019t disable yourself)" })] })] }));
}
