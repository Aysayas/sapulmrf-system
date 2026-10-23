import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Navigate } from 'react-router';
import { HOME, ROLE_LABEL, useLogout, useMe } from '../api/auth';
/** Only a logged-in user with `role` gets past this. Others go to their own side; staff screens aren't built yet. */
export default function RequireRole({ role, children }) {
    const me = useMe();
    const logout = useLogout();
    if (me.isPending)
        return _jsx("p", { className: "p-8 text-muted", children: "Loading\u2026" });
    if (me.isError)
        return _jsx("p", { className: "p-8 text-crit", children: "Can\u2019t reach the server. Check that Docker is running." });
    if (!me.data)
        return _jsx(Navigate, { to: "/login", replace: true });
    if (me.data.role === 'staff')
        return (_jsx("main", { className: "grid min-h-screen place-items-center p-4", children: _jsxs("div", { className: "max-w-md rounded-2xl bg-white p-8 text-center shadow", children: [_jsxs("h1", { className: "text-xl font-extrabold", children: ["Signed in as ", ROLE_LABEL[me.data.role]] }), _jsx("p", { className: "mt-2 text-ink-2", children: "The screens for your role aren\u2019t built yet." }), _jsx("button", { className: "mt-4 rounded-lg border border-edge px-4 py-2 font-semibold", onClick: () => logout.mutate(), children: "Log out" })] }) }));
    if (me.data.role !== role)
        return _jsx(Navigate, { to: HOME[me.data.role], replace: true });
    return children;
}
