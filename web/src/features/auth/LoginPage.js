import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useNavigate } from 'react-router';
import { z } from 'zod';
import { HOME, useLogin, useMe } from '../../api/auth';
const BALES = 'https://images.unsplash.com/photo-1764529310915-f73129d29c22?w=1800&q=70&auto=format&fit=crop';
const schema = z.object({
    username: z.string().trim().min(1, 'Enter your username.'),
    password: z.string().min(1, 'Enter your password.'),
});
export default function LoginPage() {
    const me = useMe();
    const login = useLogin();
    const navigate = useNavigate();
    const [showPw, setShowPw] = useState(false);
    const [api, setApi] = useState('checking…');
    const { register, handleSubmit, formState } = useForm({ resolver: zodResolver(schema) });
    useEffect(() => {
        fetch('/api/health')
            .then((r) => r.json())
            .then((b) => setApi(b.status === 'ok' ? 'ok' : `database ${b.db}`))
            .catch(() => setApi('unreachable'));
    }, []);
    if (me.data)
        return _jsx(Navigate, { to: HOME[me.data.role], replace: true });
    const onSubmit = (f) => login.mutate(f, { onSuccess: (u) => navigate(HOME[u.role], { replace: true }) });
    const field = 'rounded-lg border border-edge px-3 py-2 font-normal outline-leaf-700';
    return (_jsx("main", { className: "grid min-h-screen place-items-center bg-cover bg-center p-4", style: { backgroundImage: `linear-gradient(rgba(15,59,42,.78),rgba(15,59,42,.62)), url(${BALES})` }, children: _jsxs("form", { noValidate: true, className: "flex w-full max-w-sm flex-col gap-4 rounded-2xl bg-white p-8 shadow-2xl", onSubmit: handleSubmit(onSubmit), children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("span", { className: "grid size-9 place-items-center rounded-lg bg-leaf-700 text-xs font-bold text-white", children: "MRF" }), _jsxs("div", { children: [_jsx("div", { className: "font-bold", children: "SapulMRF" }), _jsx("div", { className: "text-xs text-muted", children: "Barangay Sapul, Calapan City" })] })] }), _jsx("h1", { className: "text-xl font-extrabold", children: "Log in" }), login.error && (_jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit shadow-[inset_4px_0_0_var(--color-crit)]", children: login.error.message })), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Username", _jsx("input", { ...register('username'), autoComplete: "username", className: field, "aria-invalid": !!formState.errors.username }), formState.errors.username && _jsx("span", { className: "text-xs text-crit", children: formState.errors.username.message })] }), _jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: ["Password", _jsx("input", { ...register('password'), type: showPw ? 'text' : 'password', autoComplete: "current-password", className: field, "aria-invalid": !!formState.errors.password }), formState.errors.password && _jsx("span", { className: "text-xs text-crit", children: formState.errors.password.message })] }), _jsxs("div", { className: "flex items-center justify-between gap-3 text-sm", children: [_jsxs("label", { className: "flex items-center gap-2", children: [_jsx("input", { type: "checkbox", checked: showPw, onChange: (e) => setShowPw(e.target.checked), className: "accent-leaf-700" }), "Show password"] }), _jsx("span", { className: "text-right text-muted", children: "Forgot it? Ask the administrator" })] }), _jsx("button", { type: "submit", disabled: login.isPending, className: "rounded-lg bg-leaf-700 py-2.5 font-semibold text-white hover:bg-leaf-800 disabled:opacity-60", children: login.isPending ? 'Logging in…' : 'Log in' }), _jsx("p", { className: "text-xs text-muted", children: "Only authorized barangay accounts can log in." }), _jsxs("p", { className: "border-t border-line pt-3 text-xs text-muted", "aria-live": "polite", children: ["API: ", _jsx("span", { className: api === 'ok' ? 'font-semibold text-leaf-700' : 'font-semibold text-crit', children: api })] })] }) }));
}
