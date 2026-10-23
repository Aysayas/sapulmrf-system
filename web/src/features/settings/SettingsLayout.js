import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink, Outlet } from 'react-router';
import { PageHeader } from '../../components/ui';
const TABS = [
    ['users', 'Users'],
    ['roles', 'Roles and permissions'],
    ['masterdata', 'Master data'],
    ['devices', 'IoT devices'],
    ['ranges', 'Ranges and limits'],
    ['activity', 'Activity log'],
];
export default function SettingsLayout() {
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Settings" }), _jsx("nav", { "aria-label": "Settings", className: "flex gap-1 border-b border-line", children: TABS.map(([path, label]) => (_jsx(NavLink, { to: `/admin/settings/${path}`, className: ({ isActive }) => `-mb-px border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${isActive ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`, children: label }, path))) }), _jsx(Outlet, {})] }));
}
