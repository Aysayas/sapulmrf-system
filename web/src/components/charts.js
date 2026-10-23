import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
// One series per chart, so one hue (leaf 600) and no legend; the card title names the series (dataviz skill).
const SERIES = '#2e8b5e';
const GRID = '#e7eee9';
const AXIS = { fontSize: 11, fill: '#5f6e66' };
const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' });
const time = (iso) => new Date(iso).toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' });
function TipBox({ title, value }) {
    return (_jsxs("div", { className: "rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-line", children: [_jsx("div", { className: "text-muted", children: title }), _jsx("div", { className: "font-bold text-ink", children: value })] }));
}
/** Daily kg received, last 14 days. */
export function IntakeChart({ data, height = 220 }) {
    return (_jsx(ResponsiveContainer, { width: "100%", height: height, children: _jsxs(BarChart, { data: data, margin: { top: 8, right: 4, left: 0, bottom: 0 }, barCategoryGap: 2, children: [_jsx(CartesianGrid, { vertical: false, stroke: GRID }), _jsx(XAxis, { dataKey: "day", tickFormatter: day, tick: AXIS, axisLine: false, tickLine: false, interval: "preserveStartEnd", minTickGap: 18 }), _jsx(YAxis, { tick: AXIS, axisLine: false, tickLine: false, width: 36 }), _jsx(Tooltip, { cursor: { fill: '#ddefe3', opacity: 0.6 }, content: ({ active, payload }) => active && payload?.[0] ? _jsx(TipBox, { title: day(String(payload[0].payload.day)), value: `${payload[0].value} kg received` }) : null }), _jsx(Bar, { dataKey: "kg", fill: SERIES, radius: [4, 4, 0, 0], isAnimationActive: false })] }) }));
}
/** Daily kg: actual days solid, forecast days hatched in the same hue (one series, two states; the key says which). */
export function ForecastChart({ actual, forecast, height = 240 }) {
    const data = [...actual.map((d) => ({ ...d, predicted: false })), ...forecast.map((d) => ({ ...d, predicted: true }))];
    return (_jsx(ResponsiveContainer, { width: "100%", height: height, children: _jsxs(BarChart, { data: data, margin: { top: 8, right: 4, left: 0, bottom: 0 }, barCategoryGap: 2, children: [_jsx("defs", { children: _jsxs("pattern", { id: "forecast-hatch", width: "6", height: "6", patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)", children: [_jsx("rect", { width: "6", height: "6", fill: "#ddefe3" }), _jsx("line", { x1: "0", y1: "0", x2: "0", y2: "6", stroke: SERIES, strokeWidth: "3" })] }) }), _jsx(CartesianGrid, { vertical: false, stroke: GRID }), _jsx(XAxis, { dataKey: "day", tickFormatter: day, tick: AXIS, axisLine: false, tickLine: false, minTickGap: 18 }), _jsx(YAxis, { tick: AXIS, axisLine: false, tickLine: false, width: 36 }), _jsx(Tooltip, { cursor: { fill: '#ddefe3', opacity: 0.6 }, content: ({ active, payload }) => active && payload?.[0] ? (_jsx(TipBox, { title: day(String(payload[0].payload.day)), value: `${payload[0].value} kg ${payload[0].payload.predicted ? 'predicted' : 'received'}` })) : null }), _jsx(Bar, { dataKey: "kg", radius: [4, 4, 0, 0], isAnimationActive: false, children: data.map((d) => (_jsx(Cell, { fill: d.predicted ? 'url(#forecast-hatch)' : SERIES, stroke: d.predicted ? SERIES : undefined }, d.day))) })] }) }));
}
/** Income from approved sales per month. */
export function IncomeChart({ data, height = 220 }) {
    const month = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', year: 'numeric' });
    const peso = (n) => `₱${n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return (_jsx(ResponsiveContainer, { width: "100%", height: height, children: _jsxs(BarChart, { data: data, margin: { top: 8, right: 4, left: 0, bottom: 0 }, barCategoryGap: 8, children: [_jsx(CartesianGrid, { vertical: false, stroke: GRID }), _jsx(XAxis, { dataKey: "month", tickFormatter: month, tick: AXIS, axisLine: false, tickLine: false }), _jsx(YAxis, { tick: AXIS, axisLine: false, tickLine: false, width: 52, tickFormatter: (v) => `₱${v.toLocaleString()}` }), _jsx(Tooltip, { cursor: { fill: '#ddefe3', opacity: 0.6 }, content: ({ active, payload }) => active && payload?.[0] ? _jsx(TipBox, { title: month(String(payload[0].payload.month)), value: `${peso(Number(payload[0].value))} income` }) : null }), _jsx(Bar, { dataKey: "income", fill: SERIES, radius: [4, 4, 0, 0], isAnimationActive: false })] }) }));
}
/** One compost reading over time, with the configured range shaded. */
export function ReadingChart({ data, field, unit, min, max, height = 200 }) {
    const values = data.map((d) => d[field]);
    const lo = Math.floor(Math.min(min, ...values) - 3);
    const hi = Math.ceil(Math.max(max, ...values) + 3);
    return (_jsx(ResponsiveContainer, { width: "100%", height: height, children: _jsxs(LineChart, { data: data, margin: { top: 8, right: 8, left: 0, bottom: 0 }, children: [_jsx(CartesianGrid, { vertical: false, stroke: GRID }), _jsx(ReferenceArea, { y1: min, y2: max, fill: "#ddefe3", fillOpacity: 0.6, ifOverflow: "extendDomain", label: { value: `range ${min}–${max}${unit}`, position: 'insideBottomRight', fontSize: 10, fill: '#1d6b47' } }), _jsx(XAxis, { dataKey: "at", tickFormatter: time, tick: AXIS, axisLine: false, tickLine: false, minTickGap: 40 }), _jsx(YAxis, { domain: [lo, hi], tick: AXIS, axisLine: false, tickLine: false, width: 44, unit: unit }), _jsx(Tooltip, { content: ({ active, payload }) => active && payload?.[0] ? _jsx(TipBox, { title: time(String(payload[0].payload.at)), value: `${payload[0].value}${unit}` }) : null }), _jsx(Line, { dataKey: field, stroke: SERIES, strokeWidth: 2, dot: false, isAnimationActive: false })] }) }));
}
/** A storage area's fill. Colour shows state (warn at the alert level) and the words say it too. */
export function FillBar({ area }) {
    const full = area.pct >= area.alert_pct;
    return (_jsxs("div", { className: "py-1.5", children: [_jsxs("div", { className: "flex justify-between gap-2 text-sm", children: [_jsx("span", { className: "truncate", children: area.name }), _jsxs("span", { className: `whitespace-nowrap ${full ? 'font-bold text-warn' : 'text-ink-2'}`, children: [area.pct, "% \u00B7 ", Math.round(area.kg).toLocaleString(), " / ", area.capacity_kg.toLocaleString(), " kg", full ? ' · almost full' : ''] })] }), _jsx("div", { className: "mt-1 h-2 overflow-hidden rounded-full bg-surface-2", role: "progressbar", "aria-valuenow": area.pct, "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": `${area.name} fill`, children: _jsx("div", { className: `h-full rounded-full ${full ? 'bg-warn' : 'bg-leaf-600'}`, style: { width: `${Math.min(100, area.pct)}%` } }) })] }));
}
export function Kpi({ label, value, sub }) {
    return (_jsxs("div", { className: "rounded-xl border border-line bg-white p-4", children: [_jsx("div", { className: "text-xs font-semibold text-ink-2", children: label }), _jsx("div", { className: "mt-1 text-[28px] leading-tight font-extrabold", children: value }), sub && _jsx("div", { className: "text-xs text-muted", children: sub })] }));
}
