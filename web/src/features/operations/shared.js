import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export const when = (iso) => new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
export const kg = (n) => `${(Math.round(n * 10) / 10).toLocaleString()} kg`;
export const peso = (n) => `₱${n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export function Period({ value, options, onChange }) {
    return (_jsx("div", { role: "group", "aria-label": "Period", className: "inline-flex self-start overflow-hidden rounded-lg border border-leaf-700 whitespace-nowrap", children: options.map(([label, d]) => (_jsx("button", { "aria-pressed": value === d, onClick: () => onChange(d), className: `border-r border-leaf-700 px-3.5 py-1.5 text-sm font-semibold last:border-r-0 ${value === d ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`, children: label }, label))) }));
}
/** The bordered table used across Operations, with loading, error and empty rows. */
export function Table({ label, head, state, empty, children }) {
    const row = (text, cls) => _jsx("tr", { children: _jsx("td", { colSpan: head.length, className: `px-3 py-4 ${cls}`, children: text }) });
    return (_jsx("div", { className: "overflow-x-auto rounded-xl border border-line bg-white", children: _jsxs("table", { "aria-label": label, className: "w-full text-sm", children: [_jsx("thead", { children: _jsx("tr", { className: "border-b border-line text-left text-xs text-muted", children: head.map((h) => _jsx("th", { className: "px-3 py-2 font-semibold whitespace-nowrap", children: h }, h)) }) }), _jsxs("tbody", { className: "[&>tr]:border-b [&>tr]:border-line/60 [&>tr:last-child]:border-0 [&_td]:px-3 [&_td]:py-2.5", children: [state.isPending && row('Loading…', 'text-muted'), state.error && row(state.error.message, 'text-crit'), state.count === 0 && row(empty, 'text-muted'), children] })] }) }));
}
/** A plain percentage bar for one row (compliance by purok). */
export function PctBar({ pct, label }) {
    return (_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("div", { className: "h-2 w-40 overflow-hidden rounded-full bg-surface-2", role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": label, children: _jsx("div", { className: "h-full rounded-full bg-leaf-600", style: { width: `${pct}%` } }) }), _jsxs("span", { className: "w-10 text-right font-semibold", children: [pct, "%"] })] }));
}
