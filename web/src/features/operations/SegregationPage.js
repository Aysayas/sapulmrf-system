import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useCompliance } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { kg, PctBar, Period, Table } from './shared';
const PERIODS = [['Last 7 days', 7], ['Last 30 days', 30], ['Last 90 days', 90]];
export default function SegregationPage() {
    const [days, setDays] = useState(30);
    const c = useCompliance(days);
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Segregation compliance", sub: "How many deliveries from each source area arrived already segregated" }), _jsx(Period, { value: days, options: PERIODS, onChange: setDays }), c.data && (_jsxs("div", { className: "grid grid-cols-4 gap-4", children: [_jsx(Kpi, { label: "Compliance", value: `${c.data.pct}%`, sub: `${c.data.segregated} of ${c.data.deliveries} checked deliveries` }), _jsx(Kpi, { label: "Deliveries checked", value: String(c.data.deliveries) }), _jsx(Kpi, { label: "Arrived segregated", value: String(c.data.segregated) }), _jsx(Kpi, { label: "Wet waste separated", value: kg(c.data.wet_kg_separated), sub: "from mixed deliveries" })] })), _jsx(Table, { label: "Compliance by source area", head: ['Source area', 'Deliveries checked', 'Arrived segregated', 'Compliance'], state: { isPending: c.isPending, error: c.error, count: c.data?.rows.length }, empty: "No checked deliveries in this period.", children: c.data?.rows.map((r) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: r.source_area }), _jsx("td", { children: r.deliveries }), _jsx("td", { children: r.segregated }), _jsx("td", { children: _jsx(PctBar, { pct: r.pct, label: `${r.source_area} compliance` }) })] }, r.source_area))) })] }));
}
