import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useCamera } from '../../api/operations';
import { Kpi } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { CameraTile } from '../overview/OverviewPage';
import { kg, Table } from './shared';
export default function CameraPage() {
    const cam = useCamera();
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Live camera", sub: "The sorting area camera's latest result, refreshed every 10 seconds" }), cam.error && _jsx("p", { className: "text-crit", children: cam.error.message }), cam.data && (_jsxs("div", { className: "grid grid-cols-[2fr_1fr] gap-4", children: [_jsx(CameraTile, { c: cam.data.latest, large: true }), _jsxs("div", { className: "flex flex-col gap-4", children: [_jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsx(Kpi, { label: "Classified today", value: String(cam.data.today) }), _jsx(Kpi, { label: "Waiting to confirm", value: String(cam.data.pending) })] }), _jsx(Kpi, { label: "Camera accepted today", value: `${cam.data.accepted_pct}%`, sub: "kept as suggested by the operator" }), _jsx("h3", { className: "-mb-2 text-sm font-bold", children: "In storage by material" }), _jsx(Table, { label: "In storage by material", head: ['Material', 'Bags', 'Weight'], state: { isPending: false, error: null, count: cam.data.bins.length }, empty: "No recyclable materials set up.", children: cam.data.bins.map((b) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: b.material }), _jsx("td", { children: b.bags }), _jsx("td", { children: kg(b.kg) })] }, b.material))) })] })] }))] }));
}
