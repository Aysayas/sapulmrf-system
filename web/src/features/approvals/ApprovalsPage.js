import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { OUTGOING_TYPE, useApprovals, useChangeReviews, useDecide, useReview, useWeightReviews, } from '../../api/approvals';
import { useDecideFlag, useFlags } from '../../api/insights';
import { Badge, btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { kg, peso, Table, when } from '../operations/shared';
const TABS = [
    ['outgoing', 'Outgoing'],
    ['adjustments', 'Adjustments'],
    ['weights', 'Corrected weights'],
    ['classifications', 'Corrected classifications'],
    ['flagged', 'Flagged records'],
];
const small = `${btn.base} ${btn.small}`;
export default function ApprovalsPage() {
    const [params, setParams] = useSearchParams();
    const tab = (TABS.find(([k]) => k === params.get('tab'))?.[0] ?? 'outgoing');
    const inbox = useApprovals();
    const [open, setOpen] = useState(null);
    const [toast, setToast] = useState(null);
    const state = { isPending: inbox.isPending, error: inbox.error };
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Approvals", sub: "Everything waiting for your decision, in one place." }), _jsx("div", { role: "tablist", "aria-label": "Approvals", className: "flex gap-1 border-b border-line", children: TABS.map(([key, label]) => (_jsxs("button", { role: "tab", "aria-selected": tab === key, onClick: () => setParams({ tab: key }), className: `-mb-px flex items-center gap-1.5 border-b-2 px-3.5 py-2 text-sm whitespace-nowrap ${tab === key ? 'border-leaf-700 font-bold text-leaf-700' : 'border-transparent text-ink-2 hover:text-ink'}`, children: [label, _jsx("span", { className: `rounded-full px-1.5 text-[11px] font-bold ${inbox.data?.counts[key] ? 'bg-leaf-700 text-white' : 'bg-surface-2 text-muted'}`, children: inbox.data?.counts[key] ?? '·' })] }, key))) }), tab === 'outgoing' && (_jsx(Table, { label: "Outgoing waiting for approval", head: ['No.', 'Requested', 'Type', 'Material', 'Recipient', 'Total', 'Requested by', ''], state: { ...state, count: inbox.data?.outgoing.length }, empty: "No outgoing records waiting.", children: inbox.data?.outgoing.map((o) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: o.code }), _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(o.requested_at) }), _jsx("td", { children: OUTGOING_TYPE[o.type] }), _jsxs("td", { className: "whitespace-nowrap", children: [o.material, " \u00B7 ", kg(o.kg)] }), _jsx("td", { children: o.recipient }), _jsx("td", { children: o.total === null ? '—' : peso(o.total) }), _jsx("td", { className: "text-ink-2", children: o.requested_by ?? '—' }), _jsx("td", { children: _jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Review ${o.code}`, onClick: () => setOpen({ kind: 'outgoing', row: o }), children: "Review" }) })] }, o.id))) })), tab === 'adjustments' && (_jsx(Table, { label: "Adjustments waiting for approval", head: ['Requested', 'Material', 'Storage area', 'System said', 'Counted', 'Reason', 'Requested by', ''], state: { ...state, count: inbox.data?.adjustments.length }, empty: "No adjustments waiting.", children: inbox.data?.adjustments.map((a) => (_jsxs("tr", { children: [_jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(a.requested_at) }), _jsx("td", { className: "font-semibold", children: a.material }), _jsx("td", { children: a.area }), _jsx("td", { children: kg(a.system_kg) }), _jsx("td", { children: kg(a.actual_kg) }), _jsx("td", { children: a.reason }), _jsx("td", { className: "text-ink-2", children: a.requested_by ?? '—' }), _jsx("td", { children: _jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Review adjustment of ${a.material} in ${a.area}`, onClick: () => setOpen({ kind: 'adjustments', row: a }), children: "Review" }) })] }, a.id))) })), tab === 'weights' && _jsx(WeightReviews, { onDone: setToast }), tab === 'classifications' && _jsx(ChangeReviews, { onDone: setToast }), tab === 'flagged' && _jsx(FlaggedRecords, { onDone: setToast }), open && _jsx(DecisionDrawer, { open: open, onClose: () => setOpen(null), onDone: (m) => { setOpen(null); setToast(m); } }), _jsx(Toast, { message: toast })] }));
}
function DecisionDrawer({ open, onClose, onDone }) {
    const decide = useDecide();
    const [comment, setComment] = useState('');
    const { kind, row } = open;
    const name = kind === 'outgoing' ? `${row.code} · ${OUTGOING_TYPE[row.type]}` : `Adjustment · ${row.material}, ${row.area}`;
    const short = kind === 'outgoing' && row.available_kg < row.kg;
    const [needReason, setNeedReason] = useState(false);
    const send = (decision) => decision === 'reject' && !comment.trim() ? setNeedReason(true) : decide.mutate({ kind, id: row.id, decision, comment: comment.trim() }, {
        onSuccess: () => onDone(decision === 'reject' ? `${kind === 'outgoing' ? row.code : 'Adjustment'} rejected` : approvedMessage(open)),
    });
    const facts = kind === 'outgoing'
        ? [
            ['Material', row.material],
            ['From', row.area ? `${row.area} · ${kg(row.available_kg)} in stock` : `Finished compost · ${kg(row.available_kg)} on hand`],
            ['Quantity', kg(row.kg)],
            [row.type === 'sale' ? 'Buyer' : 'Recipient', row.recipient],
            ...(row.price_per_kg !== null ? [['Price per kg', peso(row.price_per_kg)], ['Total', peso(row.total ?? 0)]] : []),
        ]
        : [
            ['Material and area', `${row.material} · ${row.area}`],
            ['System said', `${kg(row.system_kg)} when requested (${kg(row.current_kg)} now)`],
            ['Actual count', kg(row.actual_kg)],
            ['Reason', row.reason],
            ...(row.details ? [['Details', row.details]] : []),
        ];
    return (_jsxs(Drawer, { title: name, onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary}`, disabled: decide.isPending, onClick: () => send('reject'), children: "Reject" }), _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: decide.isPending || short, onClick: () => send('approve'), children: kind === 'outgoing' && row.type === 'sale' ? 'Approve sale' : 'Approve' })] }), children: [_jsxs("dl", { className: "grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 text-sm", children: [facts.map(([k, v]) => (_jsxs("div", { className: "contents", children: [_jsx("dt", { className: "text-ink-2", children: k }), _jsx("dd", { className: "font-semibold", children: v })] }, k))), _jsx("dt", { className: "text-ink-2", children: "Requested by" }), _jsxs("dd", { children: [row.requested_by ?? '—', " \u00B7 ", when(row.requested_at)] })] }), _jsx("p", { className: `rounded-lg px-3 py-2 text-sm ${short ? 'bg-crit-100 text-crit' : 'bg-surface'}`, children: afterApproval(open) }), _jsxs("label", { className: "text-sm font-semibold", children: ["Comment ", _jsx("span", { className: "font-normal text-muted", children: "(optional; say why if you reject)" }), _jsx("textarea", { className: `${inputCls} mt-1`, rows: 3, maxLength: 200, value: comment, "aria-invalid": needReason && !comment.trim(), onChange: (e) => setComment(e.target.value) })] }), needReason && !comment.trim() && _jsx("p", { role: "alert", className: "text-sm text-crit", children: "Say why you are rejecting it." }), decide.error && _jsx("p", { role: "alert", className: "text-sm text-crit", children: decide.error.message })] }));
}
function afterApproval({ kind, row }) {
    if (kind === 'outgoing' && row.available_kg < row.kg)
        return `Only ${kg(row.available_kg)} available. Reject it, or ask the operator for a new count.`;
    if (kind === 'outgoing' && row.area === null)
        return `After approval: compost on hand ${kg(row.available_kg)} → ${kg(row.available_kg - row.kg)}`;
    const after = row.area_after_kg ?? 0;
    const cap = row.capacity_kg ?? 0;
    return `After approval: ${row.area} ${kg(row.area_kg ?? 0)} → ${kg(after)} (${cap ? Math.round((after / cap) * 100) : 0}% full)`;
}
function approvedMessage({ kind, row }) {
    if (kind === 'adjustments')
        return `Adjustment approved · ${row.material} in ${row.area} is now ${kg(row.actual_kg)}`;
    return `${row.code} approved · ${kg(row.kg)} left ${row.area ?? 'compost'}${row.total !== null ? ' · income recorded' : ''}`;
}
function WeightReviews({ onDone }) {
    const list = useWeightReviews();
    const review = useReview();
    const mark = (id, code, r) => review.mutate({ kind: 'weights', id, review: r }, { onSuccess: () => onDone(`${code} marked ${r === 'ok' ? 'OK' : 'to recheck'}`) });
    return (_jsx(Table, { label: "Corrected weights", head: ['Delivery', 'Received', 'Source area', 'Scale said', 'Corrected to', 'Reason', 'By', ''], state: { isPending: list.isPending, error: list.error ?? review.error, count: list.data?.length }, empty: "No corrected weights to review.", children: list.data?.map((d) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: d.code }), _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(d.received_at) }), _jsx("td", { children: d.source_area }), _jsx("td", { children: kg(d.scale_kg ?? 0) }), _jsx("td", { className: "font-semibold", children: kg(d.weight_kg) }), _jsx("td", { children: d.correction_reason }), _jsx("td", { className: "text-ink-2", children: d.recorded_by ?? '—' }), _jsxs("td", { className: "whitespace-nowrap", children: [_jsx("button", { className: `${small} ${btn.primary}`, "aria-label": `Mark ${d.code} OK`, disabled: review.isPending, onClick: () => mark(d.id, d.code, 'ok'), children: "OK" }), ' ', _jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Ask to recheck ${d.code}`, disabled: review.isPending, onClick: () => mark(d.id, d.code, 'recheck'), children: "Ask to recheck" })] })] }, d.id))) }));
}
function FlaggedRecords({ onDone }) {
    const list = useFlags();
    const decide = useDecideFlag();
    const mark = (id, code, d) => decide.mutate({ id, decision: d }, { onSuccess: () => onDone(`${code} marked ${d}`) });
    return (_jsxs(_Fragment, { children: [_jsx("p", { className: "text-sm text-ink-2", children: "Flagged records are never changed automatically. Mark each one valid or incorrect." }), _jsx(Table, { label: "Flagged records", head: ['Record', 'Source', 'Value', 'Expected', 'Why flagged', 'Your decision'], state: { isPending: list.isPending, error: list.error ?? decide.error, count: list.data?.length }, empty: "No flagged records to review.", children: list.data?.map((f) => (_jsxs("tr", { children: [_jsxs("td", { className: "font-semibold whitespace-nowrap", children: [f.code, _jsx("span", { className: "block text-xs font-normal text-muted", children: when(f.received_at) })] }), _jsxs("td", { children: [f.source_area, " \u00B7 ", f.category] }), _jsxs("td", { className: "whitespace-nowrap", children: [kg(f.value_kg), f.kind === 'gap' ? ' received' : ''] }), _jsx("td", { children: f.expected }), _jsx("td", { children: _jsx(Badge, { kind: "warn", children: f.why }) }), _jsxs("td", { className: "whitespace-nowrap", children: [_jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Mark ${f.code} valid`, disabled: decide.isPending, onClick: () => mark(f.id, f.code, 'valid'), children: "Valid" }), ' ', _jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Mark ${f.code} incorrect`, disabled: decide.isPending, onClick: () => mark(f.id, f.code, 'incorrect'), children: "Incorrect" })] })] }, f.id))) })] }));
}
function ChangeReviews({ onDone }) {
    const list = useChangeReviews();
    const review = useReview();
    const mark = (id, r) => review.mutate({ kind: 'classifications', id, review: r }, { onSuccess: () => onDone(r === 'ok' ? 'Change marked OK' : 'Change marked wrong') });
    return (_jsx(Table, { label: "Corrected classifications", head: ['Time', 'Photo', 'Camera said', 'Operator changed to', 'Reason', 'By', ''], state: { isPending: list.isPending, error: list.error ?? review.error, count: list.data?.length }, empty: "No changed classifications to review.", children: list.data?.map((c) => (_jsxs("tr", { children: [_jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(c.confirmed_at ?? c.suggested_at) }), _jsx("td", { children: _jsx("img", { src: c.image_url, alt: `Item the camera called ${c.suggested}`, className: "h-10 w-14 rounded object-cover", loading: "lazy" }) }), _jsxs("td", { className: "whitespace-nowrap", children: [c.suggested, " \u00B7 ", Math.round(c.confidence * 100), "%"] }), _jsx("td", { children: _jsx(Badge, { kind: "warn", children: c.final }) }), _jsx("td", { children: c.reason || '—' }), _jsx("td", { className: "text-ink-2", children: c.confirmed_by ?? '—' }), _jsxs("td", { className: "whitespace-nowrap", children: [_jsx("button", { className: `${small} ${btn.primary}`, "aria-label": `Mark change to ${c.final} OK`, disabled: review.isPending, onClick: () => mark(c.id, 'ok'), children: "OK" }), ' ', _jsx("button", { className: `${small} ${btn.secondary}`, "aria-label": `Mark change to ${c.final} wrong`, disabled: review.isPending, onClick: () => mark(c.id, 'wrong'), children: "Wrong" })] })] }, c.id))) }));
}
