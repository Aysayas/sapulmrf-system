import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { useAlertSummary } from '../api/alerts';
import { useApprovals } from '../api/approvals';
import { ROLE_LABEL, useLogout, useMe } from '../api/auth';
const NAV = [
    { section: 'Monitor', items: [{ to: '/admin', label: 'Overview', end: true }, { to: '/admin/approvals', label: 'Approvals' }, { to: '/admin/alerts', label: 'Alerts' }, { to: '/admin/operations', label: 'Operations', sub: [
                    ['intake', 'Intake'], ['segregation', 'Segregation'], ['sorting', 'Sorting'], ['inventory', 'Inventory'], ['compost', 'Compost'], ['outgoing', 'Outgoing'], ['camera', 'Live camera'],
                ] }] },
    { section: 'Analyze', items: [{ to: '/admin/insights', label: 'Insights' }, { to: '/admin/reports', label: 'Reports' }] },
    { section: 'Manage', items: [{ to: '/admin/settings', label: 'Settings' }] },
];
/** The admin shell from the approved mockup: dark-green sidebar, top bar with the user menu. */
export default function AdminLayout() {
    const me = useMe().data;
    const logout = useLogout();
    const navigate = useNavigate();
    const { pathname } = useLocation();
    const counts = useApprovals().data?.counts;
    const alerts = useAlertSummary().data;
    const badges = {
        '/admin/approvals': [counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0, 'bg-leaf-600'],
        '/admin/alerts': [alerts ? alerts.unacknowledged + alerts.open_reports : 0, 'bg-crit'],
    };
    const [menu, setMenu] = useState(false);
    const initials = me.name.split(' ').map((w) => w[0]).slice(0, 2).join('');
    return (_jsxs("div", { className: "grid min-h-screen grid-cols-[232px_1fr]", children: [_jsxs("aside", { className: "flex flex-col gap-0.5 bg-leaf-900 px-3 py-4 text-[#e3efe7]", children: [_jsxs("div", { className: "flex items-center gap-2.5 px-2 pb-3.5", children: [_jsx("span", { className: "grid size-[30px] place-items-center rounded-lg bg-leaf-600 text-[11px] font-bold text-white", children: "MRF" }), _jsxs("div", { className: "font-bold", children: ["SapulMRF", _jsx("small", { className: "block text-[11px] font-normal text-[#9dbfab]", children: "Barangay Sapul MRF" })] })] }), NAV.map((g) => (_jsxs("nav", { "aria-label": g.section, children: [_jsx("div", { className: "px-2 pt-3.5 pb-1.5 text-xs font-semibold text-[#9dbfab]", children: g.section }), g.items.map((i) => (_jsxs("div", { children: [_jsxs(NavLink, { to: i.to, end: i.end, className: ({ isActive }) => `flex items-center gap-2.5 rounded-md p-2 font-medium ${isActive && !i.sub ? 'bg-leaf-100 font-bold text-leaf-900' : isActive ? 'font-bold' : 'hover:bg-white/10'}`, children: [_jsx("span", { className: "size-4 rounded border-[1.5px] border-current opacity-70", "aria-hidden": true }), i.label, badges[i.to]?.[0] > 0 && (_jsx("span", { className: `ml-auto rounded-full px-2 text-xs font-bold text-white ${badges[i.to][1]}`, "aria-label": `${badges[i.to][0]} waiting`, children: badges[i.to][0] }))] }), i.sub && pathname.startsWith(i.to) &&
                                        i.sub.map(([path, label]) => (_jsx(NavLink, { to: `${i.to}/${path}`, className: ({ isActive }) => `my-0.5 ml-6 block rounded-md px-2 py-1.5 text-sm ${isActive ? 'bg-leaf-100 font-bold text-leaf-900' : 'hover:bg-white/10'}`, children: label }, path)))] }, i.to)))] }, g.section))), _jsx("div", { className: "mt-auto px-2 text-[11px] text-[#9dbfab]", children: "SapulMRF \u00B7 v0.1" })] }), _jsxs("div", { className: "flex min-w-0 flex-col", children: [_jsxs("header", { className: "relative flex h-14 items-center gap-4 border-b border-line bg-white px-6", children: [_jsx("span", { className: "text-sm text-muted", children: "Barangay Sapul MRF" }), _jsx(Bell, {}), _jsxs("button", { className: "flex items-center gap-2 rounded-lg px-2 py-1 text-left text-xs hover:bg-surface", "aria-label": `Account menu for ${me.name}`, "aria-haspopup": "menu", "aria-expanded": menu, onClick: () => setMenu((m) => !m), children: [_jsx("span", { className: "grid size-[30px] place-items-center rounded-full bg-leaf-100 text-[11px] font-bold text-leaf-700", children: initials }), _jsxs("span", { children: [me.name, _jsx("small", { className: "block text-[11px] text-muted", children: ROLE_LABEL[me.role] })] }), _jsx("span", { "aria-hidden": true, children: "\u25BE" })] }), menu && (_jsx("div", { role: "menu", className: "absolute top-12 right-6 z-10 w-56 rounded-xl bg-white p-2 shadow-xl ring-1 ring-line", children: _jsx("button", { role: "menuitem", className: "w-full rounded-md px-3 py-2 text-left font-semibold hover:bg-surface", onClick: () => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) }), children: "Log out" }) }))] }), _jsx("main", { className: "flex flex-1 flex-col gap-4 px-6 py-5", children: _jsx(Outlet, {}) })] })] }));
}
/** Open alerts plus open problem reports, with the latest few. A count of open items, not per-person read state. */
function Bell() {
    const s = useAlertSummary().data;
    const [open, setOpen] = useState(false);
    const n = s ? s.open_alerts + s.open_reports : 0;
    return (_jsxs("div", { className: "relative ml-auto", children: [_jsxs("button", { className: "relative grid size-9 place-items-center rounded-lg hover:bg-surface", "aria-haspopup": "menu", "aria-expanded": open, "aria-label": `Alerts and problem reports, ${n} open`, onClick: () => setOpen((o) => !o), children: [_jsx("svg", { viewBox: "0 0 24 24", className: "size-5 fill-none stroke-ink-2 stroke-2", "aria-hidden": true, children: _jsx("path", { d: "M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0", strokeLinecap: "round", strokeLinejoin: "round" }) }), n > 0 && _jsx("span", { className: "absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-crit px-1 text-[10px] leading-4 font-bold text-white", children: n })] }), open && (_jsxs("div", { role: "menu", "aria-label": "Open alerts and reports", className: "absolute top-11 right-0 z-10 w-80 rounded-xl bg-white p-2 shadow-xl ring-1 ring-line", children: [s?.latest.length ? s.latest.map((i) => (_jsxs(Link, { role: "menuitem", to: `/admin/alerts?tab=${i.type === 'report' ? 'reports' : 'open'}`, onClick: () => setOpen(false), className: "block rounded-md px-3 py-2 hover:bg-surface", children: [_jsx("span", { className: "block text-sm font-semibold", children: i.title }), _jsx("span", { className: "block truncate text-xs text-muted", children: i.details })] }, `${i.type}${i.id}`))) : _jsx("p", { className: "px-3 py-2 text-sm text-ink-2", children: "Nothing open. Everything is within its limits." }), _jsx(Link, { role: "menuitem", to: "/admin/alerts", onClick: () => setOpen(false), className: "mt-1 block border-t border-line px-3 pt-2 pb-1 text-sm font-semibold text-leaf-700 underline", children: "See all alerts" })] }))] }));
}
