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

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({
    // A 401 anywhere means the session ended: re-check who is logged in, and the guard sends them to /login.
    onError: (e, query) => {
      if (e instanceof ApiError && e.status === 401 && query.queryKey[0] !== 'me') queryClient.setQueryData(['me'], null);
    },
  }),
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<RequireRole role="admin"><AdminLayout /></RequireRole>}>
            <Route index element={<OverviewPage />} />
            <Route path="approvals" element={<ApprovalsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="operations">
              <Route index element={<Navigate to="intake" replace />} />
              <Route path="intake" element={<IntakePage />} />
              <Route path="segregation" element={<SegregationPage />} />
              <Route path="sorting" element={<SortingPage />} />
              <Route path="inventory" element={<InventoryPage />} />
              <Route path="compost" element={<CompostPage />} />
              <Route path="outgoing" element={<OutgoingPage />} />
              <Route path="camera" element={<CameraPage />} />
            </Route>
            <Route path="insights" element={<InsightsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="users" replace />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="roles" element={<RolesPage />} />
              <Route path="masterdata" element={<MasterDataPage />} />
              <Route path="devices" element={<DevicesPage />} />
              <Route path="ranges" element={<RangesPage />} />
              <Route path="activity" element={<ActivityPage />} />
            </Route>
          </Route>
          <Route path="/op" element={<RequireRole role="operator"><OperatorLayout /></RequireRole>}>
            <Route index element={<Navigate to="storage" replace />} />
            <Route path="storage" element={<OpStoragePage />} />
            <Route path="outgoing" element={<OpOutgoingPage />} />
            <Route path="alerts" element={<OpAlertsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
