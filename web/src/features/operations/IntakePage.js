import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useIntake } from '../../api/operations';
import { Badge, inputCls, PageHeader } from '../../components/ui';
import { kg, Period, Table, when } from './shared';
const PERIODS = [['Today', 1], ['This week', 7], ['This month', 31], ['All', undefined]];
const STATUS = { awaiting: ['warn', 'Awaiting segregation'], separated: ['neutral', 'Separated'], sorted: ['ok', 'Sorted'] };
export default function IntakePage() {
    const [days, setDays] = useState(7);
    const [q, setQ] = useState('');
    const list = useIntake(days, q.trim());
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Intake records", sub: "Household waste deliveries weighed at the MRF, newest first (up to 100)" }), _jsxs("div", { className: "flex items-center gap-3", children: [_jsx(Period, { value: days, options: PERIODS, onChange: setDays }), _jsx("input", { type: "search", "aria-label": "Search deliveries", placeholder: "Search code, source area or category", className: `${inputCls} ml-auto w-80`, value: q, onChange: (e) => setQ(e.target.value) })] }), _jsx(Table, { label: "Deliveries", head: ['Code', 'Received', 'Source area', 'Category', 'Weight', 'Segregation', 'Status', 'Recorded by'], state: { isPending: list.isPending, error: list.error, count: list.data?.length }, empty: "No deliveries for this filter.", children: list.data?.map((d) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: d.code }), _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(d.received_at) }), _jsx("td", { children: d.source_area }), _jsx("td", { children: d.category }), _jsxs("td", { className: "whitespace-nowrap", children: [kg(d.weight_kg), ' ', d.corrected && _jsx("span", { title: d.correction_reason ?? '', children: _jsxs(Badge, { kind: "warn", children: ["Corrected from ", kg(d.scale_kg ?? 0)] }) }), d.weighed_by === 'manual' && !d.corrected && _jsx(Badge, { children: "Manual" })] }), _jsx("td", { className: "whitespace-nowrap", children: d.segregation
                                ? `${d.segregation.condition === 'segregated' ? 'Segregated' : 'Mixed'} · wet ${kg(d.segregation.wet_kg)} · dry ${kg(d.segregation.dry_kg)}`
                                : '—' }), _jsx("td", { children: _jsx(Badge, { kind: STATUS[d.status][0], children: STATUS[d.status][1] }) }), _jsx("td", { className: "text-ink-2", children: d.recorded_by ?? '—' })] }, d.id))) })] }));
}
