import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink, Outlet, useNavigate } from 'react-router';
import { useAlertSummary } from '../api/alerts';
import { ROLE_LABEL, useLogout, useMe } from '../api/auth';
const TABS = [
    ['/op/storage', 'Storage'],
    ['/op/outgoing', 'Outgoing'],
    ['/op/alerts', 'Alerts'],
];
/** The operator shell, phone first: top bar, one column, tab bar at the bottom. On a laptop it stays a centred column. */
export default function OperatorLayout() {
    const me = useMe().data;
    const logout = useLogout();
    const navigate = useNavigate();
    const alerts = useAlertSummary().data?.unacknowledged ?? 0;
    return (_jsxs("div", { className: "mx-auto flex min-h-screen max-w-[480px] flex-col bg-surface", children: [_jsxs("header", { className: "sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-line bg-white px-4", children: [_jsx("span", { className: "grid size-8 place-items-center rounded-lg bg-leaf-700 text-[11px] font-bold text-white", children: "MRF" }), _jsxs("span", { className: "min-w-0 flex-1 truncate text-sm leading-tight", children: [_jsx("b", { children: me.name }), _jsx("small", { className: "block text-xs text-muted", children: ROLE_LABEL[me.role] })] }), _jsx("button", { className: "min-h-11 rounded-lg border border-edge px-3 text-sm font-semibold", onClick: () => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) }), children: "Log out" })] }), _jsx("main", { className: "flex flex-1 flex-col gap-4 px-4 pt-4 pb-24", children: _jsx(Outlet, {}) }), _jsx("nav", { "aria-label": "Operator", className: "fixed bottom-0 left-1/2 z-10 grid w-full max-w-[480px] -translate-x-1/2 grid-cols-3 border-t border-line bg-white", children: TABS.map(([to, label]) => (_jsxs(NavLink, { to: to, className: ({ isActive }) => `flex min-h-14 items-center justify-center gap-1.5 text-sm font-semibold ${isActive ? 'bg-leaf-100 text-leaf-900' : 'text-ink-2'}`, children: [label, label === 'Alerts' && alerts > 0 && (_jsx("span", { className: "rounded-full bg-crit px-2 text-xs font-bold text-white", "aria-label": `${alerts} not acknowledged`, children: alerts }))] }, to))) })] }));
}
