import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { ApiError } from '../api/client';
import RolesPage from '../features/access/RolesPage';
import ApprovalsPage from '../features/approvals/ApprovalsPage';
import ActivityPage from '../features/activity/ActivityPage';
import AlertsPage from '../features/alerts/AlertsPage';
import LoginPage from '../features/auth/LoginPage';
import DevicesPage from '../features/devices/DevicesPage';
import InsightsPage from '../features/insights/InsightsPage';
import ReportsPage from '../features/reports/ReportsPage';
import MasterDataPage from '../features/masterdata/MasterDataPage';
import CameraPage from '../features/operations/CameraPage';
import CompostPage from '../features/operations/CompostPage';
import IntakePage from '../features/operations/IntakePage';
import InventoryPage from '../features/operations/InventoryPage';
import OutgoingPage from '../features/operations/OutgoingPage';
import SegregationPage from '../features/operations/SegregationPage';
import SortingPage from '../features/operations/SortingPage';
import OverviewPage from '../features/overview/OverviewPage';
import RangesPage from '../features/ranges/RangesPage';
import SettingsLayout from '../features/settings/SettingsLayout';
import UsersPage from '../features/users/UsersPage';
import AdminLayout from '../layout/AdminLayout';
import OperatorLayout from '../layout/OperatorLayout';
import OpAlertsPage from '../features/operator/AlertsPage';
import OpOutgoingPage from '../features/operator/OutgoingPage';
import OpStoragePage from '../features/operator/StoragePage';
import RequireRole from './RequireRole';
const queryClient = new QueryClient({
    queryCache: new QueryCache({
        // A 401 anywhere means the session ended: re-check who is logged in, and the guard sends them to /login.
        onError: (e, query) => {
            if (e instanceof ApiError && e.status === 401 && query.queryKey[0] !== 'me')
                queryClient.setQueryData(['me'], null);
        },
    }),
    defaultOptions: { queries: { refetchOnWindowFocus: false } },
});
export default function App() {
    return (_jsx(QueryClientProvider, { client: queryClient, children: _jsx(BrowserRouter, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }), _jsxs(Route, { path: "/admin", element: _jsx(RequireRole, { role: "admin", children: _jsx(AdminLayout, {}) }), children: [_jsx(Route, { index: true, element: _jsx(OverviewPage, {}) }), _jsx(Route, { path: "approvals", element: _jsx(ApprovalsPage, {}) }), _jsx(Route, { path: "alerts", element: _jsx(AlertsPage, {}) }), _jsxs(Route, { path: "operations", children: [_jsx(Route, { index: true, element: _jsx(Navigate, { to: "intake", replace: true }) }), _jsx(Route, { path: "intake", element: _jsx(IntakePage, {}) }), _jsx(Route, { path: "segregation", element: _jsx(SegregationPage, {}) }), _jsx(Route, { path: "sorting", element: _jsx(SortingPage, {}) }), _jsx(Route, { path: "inventory", element: _jsx(InventoryPage, {}) }), _jsx(Route, { path: "compost", element: _jsx(CompostPage, {}) }), _jsx(Route, { path: "outgoing", element: _jsx(OutgoingPage, {}) }), _jsx(Route, { path: "camera", element: _jsx(CameraPage, {}) })] }), _jsx(Route, { path: "insights", element: _jsx(InsightsPage, {}) }), _jsx(Route, { path: "reports", element: _jsx(ReportsPage, {}) }), _jsxs(Route, { path: "settings", element: _jsx(SettingsLayout, {}), children: [_jsx(Route, { index: true, element: _jsx(Navigate, { to: "users", replace: true }) }), _jsx(Route, { path: "users", element: _jsx(UsersPage, {}) }), _jsx(Route, { path: "roles", element: _jsx(RolesPage, {}) }), _jsx(Route, { path: "masterdata", element: _jsx(MasterDataPage, {}) }), _jsx(Route, { path: "devices", element: _jsx(DevicesPage, {}) }), _jsx(Route, { path: "ranges", element: _jsx(RangesPage, {}) }), _jsx(Route, { path: "activity", element: _jsx(ActivityPage, {}) })] })] }), _jsxs(Route, { path: "/op", element: _jsx(RequireRole, { role: "operator", children: _jsx(OperatorLayout, {}) }), children: [_jsx(Route, { index: true, element: _jsx(Navigate, { to: "storage", replace: true }) }), _jsx(Route, { path: "storage", element: _jsx(OpStoragePage, {}) }), _jsx(Route, { path: "outgoing", element: _jsx(OpOutgoingPage, {}) }), _jsx(Route, { path: "alerts", element: _jsx(OpAlertsPage, {}) })] }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/login", replace: true }) })] }) }) }));
}
