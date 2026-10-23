import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
export default function ComingSoon({ title, phase }) {
    return (_jsxs(_Fragment, { children: [_jsx("h1", { className: "text-2xl font-extrabold", children: title }), _jsx("div", { className: "grid flex-1 place-items-center rounded-xl border border-dashed border-edge bg-white p-8 text-center text-ink-2", children: _jsxs("div", { children: [_jsxs("b", { className: "block text-ink", children: ["Coming in Phase ", phase] }), "This screen is designed in the prototype and gets built in a later phase of the roadmap."] }) })] }));
}
