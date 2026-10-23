import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { useItems } from '../../api/masterdata';
import { useExportReport, useRecentReports, useReport } from '../../api/reports';
import { btn, inputCls, PageHeader, Toast } from '../../components/ui';
import { Table, when } from '../operations/shared';
const KINDS = [
    ['intake', 'Intake', 'Deliveries and weights per purok and category'],
    ['segregation', 'Segregation', 'Compliance per purok'],
    ['inventory', 'Inventory', 'Stock per material and area, as of now'],
    ['composting', 'Composting', 'Batches, readings, compost produced'],
    ['outgoing', 'Outgoing material', 'Sales, compost, residual'],
    ['income', 'Income', 'Income from recyclables and compost'],
];
const BY_AREA = ['intake', 'segregation'];
/** A Manila calendar day as YYYY-MM-DD, `back` days ago. */
const manilaDay = (back = 0) => new Date(Date.now() - back * 86_400_000).toLocaleDateString('en-CA', { timeZone: 'Asia/Manila' });
const dayLabel = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' });
export default function ReportsPage() {
    const [form, setForm] = useState({ kind: 'segregation', from: manilaDay(29), to: manilaDay(), area: 0 });
    const [shown, setShown] = useState(null);
    const [done, setDone] = useState(null);
    const exp = useExportReport();
    const run = (p, format, title) => exp.mutate({ ...p, format }, { onSuccess: () => setDone(`${title} exported as ${format.toUpperCase()}`) });
    return (_jsxs(_Fragment, { children: [shown ? _jsx(Preview, { p: shown, onBack: () => setShown(null), onExport: run, busy: exp.isPending })
                : _jsx(Choose, { form: form, setForm: setForm, onPreview: () => setShown(form), onExport: run }), exp.error && _jsx("p", { role: "alert", className: "text-sm text-crit", children: exp.error.message }), _jsx(Toast, { message: done })] }));
}
function Choose({ form, setForm, onPreview, onExport }) {
    const puroks = useItems('puroks');
    const recent = useRecentReports();
    const byArea = BY_AREA.includes(form.kind);
    const bad = !form.from || !form.to || form.to < form.from;
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Reports", sub: "Pick a report and a date range." }), _jsx("div", { role: "radiogroup", "aria-label": "Report", className: "grid grid-cols-3 gap-3", children: KINDS.map(([k, label, sub]) => (_jsxs("button", { role: "radio", "aria-checked": form.kind === k, onClick: () => setForm({ ...form, kind: k }), className: `rounded-xl border bg-white p-4 text-left ${form.kind === k ? 'border-leaf-700 ring-2 ring-leaf-700' : 'border-line hover:border-edge'}`, children: [_jsx("span", { className: "block font-bold", children: label }), _jsx("span", { className: "text-sm text-ink-2", children: sub })] }, k))) }), _jsxs("div", { className: "flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-4", children: [_jsxs("label", { className: "text-sm font-semibold", children: ["From", _jsx("input", { type: "date", className: `${inputCls} mt-1 w-44`, value: form.from, max: form.to, disabled: form.kind === 'inventory', onChange: (e) => setForm({ ...form, from: e.target.value }) })] }), _jsxs("label", { className: "text-sm font-semibold", children: ["To", _jsx("input", { type: "date", className: `${inputCls} mt-1 w-44`, value: form.to, min: form.from, disabled: form.kind === 'inventory', onChange: (e) => setForm({ ...form, to: e.target.value }) })] }), _jsxs("label", { className: "text-sm font-semibold", children: ["Source area", _jsxs("select", { className: `${inputCls} mt-1 w-48`, value: byArea ? form.area : 0, disabled: !byArea, onChange: (e) => setForm({ ...form, area: Number(e.target.value) }), children: [_jsx("option", { value: 0, children: "All puroks" }), puroks.data?.filter((p) => p.active).map((p) => _jsx("option", { value: p.id, children: p.name }, p.id))] })] }), _jsx("button", { className: `${btn.base} ${btn.primary} ml-auto`, disabled: bad, onClick: onPreview, children: "Preview report" })] }), form.kind === 'inventory' && _jsx("p", { className: "-mt-2 text-xs text-muted", children: "Inventory shows the stock now, so it has no date range." }), !byArea && form.kind !== 'inventory' && _jsx("p", { className: "-mt-2 text-xs text-muted", children: "This report covers the whole MRF, not one purok." }), _jsx("h2", { className: "mt-2 text-lg font-bold", children: "Recent reports" }), _jsx(Table, { label: "Recent reports", head: ['Report', 'Range', 'Source area', 'Format', 'By', 'Created', ''], state: { isPending: recent.isPending, error: recent.error, count: recent.data?.length }, empty: "No reports exported yet.", children: recent.data?.map((r) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: r.title }), _jsx("td", { className: "whitespace-nowrap", children: r.kind === 'inventory' ? 'As of export' : `${dayLabel(r.from_day)} – ${dayLabel(r.to_day)}` }), _jsx("td", { children: BY_AREA.includes(r.kind) ? r.area : '—' }), _jsx("td", { children: r.format.toUpperCase() }), _jsx("td", { children: r.by }), _jsx("td", { className: "whitespace-nowrap", children: when(r.created_at) }), _jsx("td", { className: "text-right", children: _jsx("button", { className: `${btn.base} ${btn.secondary} ${btn.small}`, title: "Rebuilt from the current data", onClick: () => onExport({ kind: r.kind, from: r.from_day, to: r.to_day, area: r.area_id ?? 0 }, r.format, r.title), children: "Download" }) })] }, r.id))) })] }));
}
function Preview({ p, onBack, onExport, busy }) {
    const r = useReport(p);
    const title = r.data?.title ?? 'Report';
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: title, sub: r.data?.subtitle, actions: _jsxs(_Fragment, { children: [_jsx("button", { className: `${btn.base} ${btn.secondary}`, onClick: onBack, children: "Back" }), _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: !r.data || busy, onClick: () => onExport(p, 'pdf', title), children: "Export PDF" }), _jsx("button", { className: `${btn.base} ${btn.primary}`, disabled: !r.data || busy, onClick: () => onExport(p, 'csv', title), children: "Export CSV" })] }) }), r.data && (_jsx("dl", { className: "flex flex-wrap gap-3", children: r.data.summary.map(([k, v]) => (_jsxs("div", { className: "min-w-36 rounded-xl border border-line bg-white px-4 py-3", children: [_jsx("dt", { className: "text-xs text-muted", children: k }), _jsx("dd", { className: "text-xl font-extrabold", children: v })] }, k))) })), _jsx(Table, { label: title, head: r.data?.columns ?? [], state: { isPending: r.isPending, error: r.error, count: r.data?.rows.length }, empty: "No records in this range.", children: r.data?.rows.map((row, i) => (_jsx("tr", { children: row.map((c, j) => _jsx("td", { className: typeof c === 'number' ? 'tabular-nums' : '', children: c === '' ? '—' : c.toLocaleString() }, j)) }, i))) }), r.data && r.data.total_rows > r.data.rows.length && (_jsxs("p", { className: "text-xs text-muted", children: ["Showing the first ", r.data.rows.length, " of ", r.data.total_rows, " rows. The PDF and CSV have all of them."] }))] }));
}
