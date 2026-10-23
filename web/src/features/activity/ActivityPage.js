import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { activityQuery, useActivity } from '../../api/activity';
import { download } from '../../api/client';
import { useUsers } from '../../api/users';
import { btn, inputCls } from '../../components/ui';
const PERIODS = [
    ['Today', 1],
    ['This week', 7],
    ['This month', 31],
    ['All', 0],
    ['Custom', -1],
];
const CATEGORIES = [
    ['', 'All actions'], ['logins', 'Logins'], ['users', 'Users and access'], ['approvals', 'Approvals and reviews'],
    ['reports', 'Reports'], ['records', 'Records and setup'],
];
const fieldCls = inputCls.replace('w-full', 'w-auto'); // the filters sit side by side and wrap
const when = (iso) => new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
export default function ActivityPage() {
    const [days, setDays] = useState(7);
    const [userId, setUserId] = useState(0);
    const [from, setFrom] = useState('');
    const [to, setTo] = useState('');
    const [category, setCategory] = useState('');
    const [exportError, setExportError] = useState(null);
    const users = useUsers();
    const custom = days === -1;
    const filters = { days: days > 0 ? days : undefined, userId: userId || undefined, category,
        from: custom ? from : undefined, to: custom ? to : undefined };
    const activity = useActivity(filters);
    const exportCsv = () => {
        setExportError(null);
        download(`/activity/export?${activityQuery(filters)}`).catch((e) => setExportError(e.message));
    };
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "flex flex-wrap items-center gap-3", children: [_jsx("div", { role: "group", "aria-label": "Period", className: "inline-flex overflow-hidden rounded-lg border border-leaf-700", children: PERIODS.map(([label, d]) => (_jsx("button", { "aria-pressed": days === d, onClick: () => setDays(d), className: `border-r border-leaf-700 px-3.5 py-1.5 text-sm font-semibold last:border-r-0 ${days === d ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`, children: label }, label))) }), custom && (_jsxs(_Fragment, { children: [_jsx("input", { type: "date", "aria-label": "From", className: `${fieldCls}`, value: from, max: to || undefined, onChange: (e) => setFrom(e.target.value) }), _jsx("span", { className: "text-sm text-muted", children: "to" }), _jsx("input", { type: "date", "aria-label": "To", className: `${fieldCls}`, value: to, min: from || undefined, onChange: (e) => setTo(e.target.value) })] })), _jsx("select", { "aria-label": "Action", className: `${fieldCls} ml-auto`, value: category, onChange: (e) => setCategory(e.target.value), children: CATEGORIES.map(([v, label]) => _jsx("option", { value: v, children: label }, v)) }), _jsxs("select", { "aria-label": "User", className: `${fieldCls}`, value: userId, onChange: (e) => setUserId(Number(e.target.value)), children: [_jsx("option", { value: 0, children: "All users" }), users.data?.map((u) => (_jsx("option", { value: u.id, children: u.name }, u.id)))] }), _jsx("button", { className: `${btn.base} ${btn.secondary}`, onClick: exportCsv, children: "Export CSV" })] }), exportError && _jsx("p", { role: "alert", className: "text-sm text-crit", children: exportError }), activity.data?.length === 100 && _jsx("p", { className: "text-xs text-muted", children: "Showing the latest 100. Export CSV has every matching row." }), _jsx("div", { className: "overflow-hidden rounded-xl border border-line bg-white", children: _jsxs("table", { className: "w-full text-sm", children: [_jsx("thead", { children: _jsx("tr", { className: "border-b border-line text-left text-xs text-muted", children: ['When', 'Who', 'Action', 'Record'].map((h) => (_jsx("th", { className: "px-3 py-2 font-semibold", children: h }, h))) }) }), _jsxs("tbody", { children: [activity.isPending && _jsx("tr", { children: _jsx("td", { colSpan: 4, className: "px-3 py-4 text-muted", children: "Loading\u2026" }) }), activity.isError && _jsx("tr", { children: _jsx("td", { colSpan: 4, className: "px-3 py-4 text-crit", children: activity.error.message }) }), activity.data?.length === 0 && _jsx("tr", { children: _jsx("td", { colSpan: 4, className: "px-3 py-4 text-muted", children: "Nothing recorded for this filter." }) }), activity.data?.map((a) => (_jsxs("tr", { className: "border-b border-line/60 last:border-0", children: [_jsx("td", { className: "px-3 py-2.5 whitespace-nowrap text-ink-2", children: when(a.at) }), _jsx("td", { className: "px-3 py-2.5", children: a.who }), _jsx("td", { className: "px-3 py-2.5 font-semibold", children: a.action }), _jsx("td", { className: "px-3 py-2.5 text-ink-2", children: a.record || '—' })] }, a.id)))] })] }) })] }));
}
