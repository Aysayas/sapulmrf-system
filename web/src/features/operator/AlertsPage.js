import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useAcknowledge, useAlerts, useMyProblems, useReportProblem } from '../../api/alerts';
import { useDevices } from '../../api/devices';
import { useIntake } from '../../api/operations';
import { btn, Drawer, inputCls, PageHeader, Toast } from '../../components/ui';
import { Period, when } from '../operations/shared';
import { Card, Field, StatusBadge, touch } from './shared';
const STATES = [['Open', 'open'], ['Acknowledged', 'acknowledged'], ['Resolved', 'resolved']];
export default function AlertsPage() {
    const [state, setState] = useState('open');
    const alerts = useAlerts(state);
    const ack = useAcknowledge();
    const mine = useMyProblems();
    const [reporting, setReporting] = useState(false);
    const [done, setDone] = useState(null);
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Alerts", sub: "Compost out of range, disconnected devices and full storage areas." }), _jsx("button", { className: `${btn.base} ${btn.secondary} ${touch} w-full`, onClick: () => setReporting(true), children: "Report a problem" }), _jsx(Period, { value: state, options: STATES, onChange: setState }), _jsxs("ul", { "aria-label": "Alerts", className: "flex flex-col gap-2", children: [alerts.isPending && _jsx("li", { className: "text-muted", children: "Loading\u2026" }), alerts.data?.length === 0 && _jsxs("li", { className: "text-muted", children: ["No ", state, " alerts."] }), alerts.data?.map((a) => (_jsxs(Card, { label: a.title, children: [_jsx("b", { className: "block", children: a.title }), _jsx("p", { className: "text-sm text-ink-2", children: a.details }), _jsxs("p", { className: "text-xs text-muted", children: ["Since ", when(a.opened_at), a.acknowledged_by ? ` · seen by ${a.acknowledged_by}` : ''] }), !a.acknowledged_at && (_jsx("button", { className: `${btn.base} ${btn.primary} ${touch} mt-2 w-full`, disabled: ack.isPending, onClick: () => ack.mutate(a.id, { onSuccess: () => setDone(`Acknowledged · ${a.title}`) }), children: "Acknowledge" }))] }, a.id)))] }), ack.error && _jsx("p", { role: "alert", className: "text-sm text-crit", children: ack.error.message }), _jsx("h2", { className: "text-lg font-bold", children: "My reports" }), _jsxs("ul", { "aria-label": "My reports", className: "flex flex-col gap-2", children: [mine.data?.length === 0 && _jsx("li", { className: "text-muted", children: "No problem reports in the last 30 days." }), mine.data?.map((r) => (_jsxs(Card, { label: r.code, children: [_jsxs("div", { className: "flex items-start gap-2", children: [_jsxs("b", { className: "flex-1", children: [r.code, " \u00B7 ", r.kind === 'device' ? r.device : r.record_ref] }), _jsx(StatusBadge, { status: r.status })] }), _jsx("p", { className: "text-sm text-ink-2", children: r.details }), _jsxs("p", { className: "text-xs text-muted", children: ["Sent ", when(r.reported_at), r.resolved_by ? ` · resolved by ${r.resolved_by}` : ''] }), r.note && _jsxs("p", { className: "mt-1 text-sm", children: ["\u201C", r.note, "\u201D"] })] }, r.id)))] }), reporting && _jsx(ReportSheet, { onClose: () => setReporting(false), onSent: (m) => { setReporting(false); setDone(m); } }), _jsx(Toast, { message: done })] }));
}
// Mirrors ProblemIn on the server.
const schema = z.object({
    kind: z.enum(['device', 'record']),
    device_id: z.number(),
    record_ref: z.string().trim().max(40),
    details: z.string().trim().min(1, 'Say what is wrong.').max(300),
}).superRefine((f, ctx) => {
    if (f.kind === 'device' && !f.device_id)
        ctx.addIssue({ code: 'custom', path: ['device_id'], message: 'Pick the device.' });
    if (f.kind === 'record' && !f.record_ref)
        ctx.addIssue({ code: 'custom', path: ['record_ref'], message: 'Say which record, for example D-0139.' });
});
function ReportSheet({ onClose, onSent }) {
    const devices = useDevices();
    const recent = useIntake(3);
    const send = useReportProblem();
    const { register, handleSubmit, formState, watch } = useForm({
        resolver: zodResolver(schema),
        defaultValues: { kind: 'record', device_id: 0, record_ref: '', details: '' },
    });
    const kind = watch('kind');
    const e = formState.errors;
    const onSubmit = (f) => send.mutate({ kind: f.kind, device_id: f.kind === 'device' ? f.device_id : null, record_ref: f.kind === 'record' ? f.record_ref : '', details: f.details }, { onSuccess: (r) => onSent(`${r.code} sent to the administrator`) });
    return (_jsxs(Drawer, { title: "Report a problem", onClose: onClose, footer: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary} ${touch}`, onClick: onClose, children: "Cancel" }), _jsx("button", { className: `${btn.base} ${btn.primary} ${touch}`, disabled: send.isPending, onClick: handleSubmit(onSubmit), children: "Send to administrator" })] }), children: [send.error && _jsx("p", { role: "alert", className: "rounded-lg bg-crit-100 px-3 py-2 text-sm font-semibold text-crit", children: send.error.message }), _jsxs("fieldset", { className: "flex flex-col gap-1", children: [_jsx("legend", { className: "mb-1 text-sm font-semibold", children: "What is wrong?" }), [['record', 'Incorrect record'], ['device', 'Device problem']].map(([v, label]) => (_jsxs("label", { className: `${touch} flex items-center gap-2 rounded-lg border border-line px-3 text-sm`, children: [_jsx("input", { type: "radio", value: v, className: "accent-leaf-700", ...register('kind') }), " ", label] }, v)))] }), kind === 'device' ? (_jsx(Field, { label: "Which device?", error: e.device_id?.message, children: _jsxs("select", { className: inputCls, "aria-invalid": !!e.device_id, ...register('device_id', { valueAsNumber: true }), children: [_jsx("option", { value: 0, children: "Pick a device" }), devices.data?.filter((d) => d.active).map((d) => (_jsxs("option", { value: d.id, children: [d.code, d.location ? ` · ${d.location}` : '', " \u00B7 ", d.status] }, d.id)))] }) })) : (_jsxs(Field, { label: "Which record?", error: e.record_ref?.message, children: [_jsx("input", { list: "recent-records", className: `${inputCls} uppercase`, placeholder: "e.g. D-0139", "aria-invalid": !!e.record_ref, ...register('record_ref') }), _jsx("datalist", { id: "recent-records", children: recent.data?.map((d) => _jsx("option", { value: d.code, children: `${d.source_area} · ${d.weight_kg} kg` }, d.id)) })] })), _jsx(Field, { label: kind === 'record' ? 'What should it be?' : 'What is happening?', error: e.details?.message, children: _jsx("textarea", { rows: 3, className: inputCls, "aria-invalid": !!e.details, placeholder: kind === 'record' ? 'e.g. Weight should be 4.10 kg, typo' : 'e.g. Scale shows 0 kg with a bag on it', ...register('details') }) })] }));
}
