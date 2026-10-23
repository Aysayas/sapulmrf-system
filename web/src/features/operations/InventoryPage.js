import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useInventory } from '../../api/operations';
import { FillBar } from '../../components/charts';
import { PageHeader } from '../../components/ui';
import { kg, Table, when } from './shared';
export default function InventoryPage() {
    const inv = useInventory();
    return (_jsxs(_Fragment, { children: [_jsx(PageHeader, { title: "Inventory", sub: "Sorted materials in storage, by storage area" }), _jsxs("section", { "aria-label": "Storage areas", className: "grid grid-cols-2 gap-x-8 rounded-xl border border-line bg-white p-4", children: [inv.data?.areas.map((a) => _jsx(FillBar, { area: a }, a.id)), inv.data?.areas.length === 0 && _jsx("p", { className: "text-sm text-ink-2", children: "No storage areas yet. Add them in Settings \u203A Master data." })] }), _jsx(Table, { label: "Stock", head: ['Material', 'Storage area', 'Bags', 'Weight', 'Last change'], state: { isPending: inv.isPending, error: inv.error, count: inv.data?.stock.length }, empty: "Nothing in storage.", children: inv.data?.stock.map((r) => (_jsxs("tr", { children: [_jsx("td", { className: "font-semibold", children: r.material }), _jsx("td", { children: r.area }), _jsx("td", { children: r.bags }), _jsx("td", { children: kg(r.kg) }), _jsx("td", { className: "whitespace-nowrap text-ink-2", children: when(r.last_change) })] }, `${r.material}|${r.area}`))) })] }));
}
