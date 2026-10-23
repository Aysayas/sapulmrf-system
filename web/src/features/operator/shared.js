import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Badge } from '../../components/ui';
const STATUS = {
    pending: ['warn', 'Pending approval'],
    approved: ['ok', 'Approved'],
    rejected: ['crit', 'Rejected'],
    open: ['warn', 'Open'],
    resolved: ['ok', 'Resolved'],
};
export function StatusBadge({ status }) {
    const [kind, label] = STATUS[status];
    return _jsx(Badge, { kind: kind, children: label });
}
/** A labelled form field with its error under it. */
export function Field({ label, error, children }) {
    return (_jsxs("label", { className: "flex flex-col gap-1 text-sm font-semibold", children: [label, children, error && _jsx("span", { className: "text-xs font-normal text-crit", children: error })] }));
}
/** One card in a phone list. */
export function Card({ children, label }) {
    return _jsx("li", { "aria-label": label, className: "rounded-xl border border-line bg-white p-3", children: children });
}
export const touch = 'min-h-11';
