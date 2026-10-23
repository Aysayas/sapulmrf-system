import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { useAcknowledge, useAlerts, useAlertSummary, useProblems, useResolveProblem } from '../../api/alerts';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { Table, when } from '../operations/shared';
const TABS = [
    ['open', 'Open'],
    ['reports', 'Problem reports'],
    ['acknowledged', 'Acknowledged'],
    ['resolved', 'Resolved'],
];
const KIND = { compost: 'Compost', device: 'Device', storage: 'Storage' };
const small = `${btn.base} ${btn.small}`;
export default function AlertsPage() {
    const [params, setParams] = useSearchParams();
    const tab = TABS.find(([k]) => k === params.get('tab'))?.[0] ?? 'open';
    const summary = useAlertSummary().data;
    const [toast, setToast] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Alerts", sub: "Compost out of range, devices that stopped reporting, storage areas almost full, and problem reports from operators." }), _jsx("div", { role: "tablist", "aria-label": "Alerts", className: "flex gap-1 border-b border-line", children: TABS.map(([key, label]) => {
                    const n = key === 'open' ? summary?.unacknowledged : key === 'reports' ? summary?.open_reports : undefined;
                    return (_jsxs("button", { role: "tab", "aria-selected": tab === key, onClick: () => setParams({ tab: key }), className: `-mb-px flex items-center gap-1.5 border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${tab === key ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`, children: [label, n !== undefined && (_jsx("span", { className: `rounded-full px-1.5 text-[11px] font-bold ${n ? 'bg-crit text-white' : 'bg-surface-2 text-muted'}`, children: n }))] }, key));
                }) }), tab === 'reports' ? _jsx(Reports, { onDone: setToast }) : _jsx(AlertTable, { state: tab, onDone: setToast }), _jsx(Toast, { message: toast })] }));
}
function AlertTable({ state, onDone }) {
    const list = useAlerts(state);
    const ack = useAcknowledge();
    const head = state === 'resolved' ? ['Alert', 'Details', 'Since', 'Cleared', 'Seen by'] : ['Alert', 'Details', 'Since', 'Seen by', ''];
    const empty = { open: 'No open alerts. Everything is within its limits.', acknowledged: 'No acknowledged alerts still open.', resolved: 'Nothing cleared in the last 30 days.' }[state];
    return (_jsxs(_Fragment, { children: [_jsx(Table, { label: `${state[0].toUpperCase()}${state.slice(1)} alerts`, head: head, state: { isPending: list.isPending, error: list.error ?? ack.error, count: list.data?.length }, empty: empty, children: list.data?.map((a) => (_jsxs("tr", { children: [_jsxs("td", { className: "font-semibold", children: [_jsx(Badge, { kind: state === 'resolved' ? 'neutral' : 'crit', children: KIND[a.kind] }), " ", a.title] }), _jsx("td", { children: a.details }), _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(a.opened_at) }), state === 'resolved' && _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(a.resolved_at) }), _jsx("td", { className: "text-ink-2", children: a.acknowledged_by ? `${a.acknowledged_by} · ${when(a.acknowledged_at)}` : '—' }), state !== 'resolved' && (_jsx("td", { children: state === 'open' && (_jsx("button", { className: `${small} ${btn.primary}`, "aria-label": `Acknowledge ${a.title}`, disabled: ack.isPending, onClick: () => ack.mutate(a.id, { onSuccess: () => onDone(`${a.title}: acknowledged`) }), children: "Acknowledge" })) }))] }, a.id))) }), state !== 'resolved' && _jsx("p", { className: "text-xs text-muted", children: "An alert stays here until its condition clears, even after it is acknowledged." })] }));
}
function Reports({ onDone }) {
    const [status, setStatus] = useState('open');
    const list = useProblems(status);
    const [open, setOpen] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx("div", { role: "group", "aria-label": "Report status", className: "inline-flex self-start overflow-hidden rounded-lg border border-leaf-700 whitespace-nowrap", children: ['open', 'resolved'].map((s) => (_jsx("button", { "aria-pressed": status === s, onClick: () => setStatus(s), className: `border-r border-leaf-700 px-3.5 py-1.5 text-sm font-semibold last:border-r-0 ${status === s ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`, children: s === 'open' ? 'Open' : 'Resolved' }, s))) }), _jsx(Table, { label: "Problem reports", head: ['Report', 'What', 'Device or record', 'Details', 'From', 'When', status === 'open' ? '' : 'Resolution'], state: { isPending: list.isPending, error: list.error, count: list.data?.length }, empty: status === 'open' ? 'No open problem reports.' : 'No resolved reports yet.', children: list.data?.map((p) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold whitespace-nowrap", children: p.code }), _jsx("td", { children: p.kind === 'device' ? 'Device problem' : 'Incorrect record' }), _jsx("td", { className: "font-semibold", children: p.device ?? p.record_ref }), _jsx("td", { children: p.details }), _jsx("td", { className: "text-ink-2", children: p.reported_by ?? '—' }), _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(p.reported_at) }), _jsx("td", { children: status === 'open'
                                ? _jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Resolve ${p.code}`, onClick: () => setOpen(p), children: "Resolve" })
                                : _jsxs("span", { className: "text-ink-2", children: [p.note, " \u00B7 ", p.resolved_by] }) })] }, p.id))) }), open && _jsx(ResolveDrawer, { report: open, onClose: () => setOpen(null), onDone: (m) => { setOpen(null); onDone(m); } })] }));
}
function ResolveDrawer({ report, onClose, onDone }) {
    const resolve = useResolveProblem();
    const [note, setNote] = useState('');
    const [tried, setTried] = useState(false);
    const send = () => (note.trim() ? resolve.mutate({ id: report.id, note: note.trim() }, { onSuccess: () => onDone(`${report.code} resolved`) }) : setTried(true));
    return (_jsxs(Drawer, { title: `${report.code} · ${report.kind === 'device' ? 'Device problem' : 'Incorrect record'}`, onClose: onClose, footer: _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: resolve.isPending, onClick: send, children: "Mark resolved" }), children: [_jsxs("dl", { className: "grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 text-sm", children: [_jsx("dt", { className: "text-ink-2", children: report.kind === 'device' ? 'Device' : 'Record' }), _jsx("dd", { className: "font-semibold", children: report.device ?? report.record_ref }), _jsx("dt", { className: "text-ink-2", children: "What's wrong" }), _jsx("dd", { children: report.details }), _jsx("dt", { className: "text-ink-2", children: "Reported by" }), _jsxs("dd", { children: [report.reported_by ?? '—', " \u00B7 ", when(report.reported_at)] })] }), report.kind === 'record' && (_jsx("p", { className: "rounded-lg bg-surface px-3 py-2 text-sm", children: "Fixing the record itself is a separate step, for example an inventory adjustment. Say what you did in the note." })), _jsxs("label", { className: "text-sm font-semibold", children: ["What was done", _jsx("textarea", { className: `${inputCls} mt-1`, rows: 3, maxLength: 200, value: note, "aria-invalid": tried && !note.trim(), onChange: (e) => setNote(e.target.value) })] }), tried && !note.trim() && _jsx("p", { role: "alert", className: "text-sm text-crit", children: "Say what was done before marking it resolved." }), resolve.error && _jsx("p", { role: "alert", className: "text-sm text-crit", children: resolve.error.message })] }));
}
