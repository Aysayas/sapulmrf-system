import { lazy } from 'react';
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { ApiError } from '../api/client';
import LoginPage from '../features/auth/LoginPage';
import AdminLayout from '../layout/AdminLayout';
import OperatorLayout from '../layout/OperatorLayout';
import StaffLayout from '../layout/StaffLayout';
import RequireRole from './RequireRole';

const RolesPage = lazy(() => import('../features/access/RolesPage'));
const ApprovalsPage = lazy(() => import('../features/approvals/ApprovalsPage'));
const ActivityPage = lazy(() => import('../features/activity/ActivityPage'));
const AlertsPage = lazy(() => import('../features/alerts/AlertsPage'));
const DevicesPage = lazy(() => import('../features/devices/DevicesPage'));
const InsightsPage = lazy(() => import('../features/insights/InsightsPage'));
const ReportsPage = lazy(() => import('../features/reports/ReportsPage'));
const MasterDataPage = lazy(() => import('../features/masterdata/MasterDataPage'));
const CameraPage = lazy(() => import('../features/operations/CameraPage'));
const CompostPage = lazy(() => import('../features/operations/CompostPage'));
const IntakePage = lazy(() => import('../features/operations/IntakePage'));
const InventoryPage = lazy(() => import('../features/operations/InventoryPage'));
const OutgoingPage = lazy(() => import('../features/operations/OutgoingPage'));
const SegregationPage = lazy(() => import('../features/operations/SegregationPage'));
const SortingPage = lazy(() => import('../features/operations/SortingPage'));
const OverviewPage = lazy(() => import('../features/overview/OverviewPage'));
const RangesPage = lazy(() => import('../features/ranges/RangesPage'));
const SettingsLayout = lazy(() => import('../features/settings/SettingsLayout'));
const UsersPage = lazy(() => import('../features/users/UsersPage'));
const OpAlertsPage = lazy(() => import('../features/operator/AlertsPage'));
const OpOutgoingPage = lazy(() => import('../features/operator/OutgoingPage'));
const OpCompostPage = lazy(() => import('../features/operator/CompostPage'));
const OpHistoryPage = lazy(() => import('../features/operator/HistoryPage'));
const OpIntakePage = lazy(() => import('../features/operator/IntakePage'));
const OpMorePage = lazy(() => import('../features/operator/MorePage'));
const OpProfilePage = lazy(() => import('../features/operator/ProfilePage'));
const OpSegregationPage = lazy(() => import('../features/operator/SegregationPage'));
const OpSortingPage = lazy(() => import('../features/operator/SortingPage'));
const OpStoragePage = lazy(() => import('../features/operator/StoragePage'));
const OpTodayPage = lazy(() => import('../features/operator/TodayPage'));
const StaffNotificationsPage = lazy(() => import('../features/staff/NotificationsPage'));
const StaffOverviewPage = lazy(() => import('../features/staff/OverviewPage'));
const StaffRecordsPage = lazy(() => import('../features/staff/RecordsPage'));
const StaffReportsPage = lazy(() => import('../features/staff/ReportsPage'));

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
            <Route index element={<Navigate to="today" replace />} />
            <Route path="today" element={<OpTodayPage />} />
            <Route path="intake" element={<OpIntakePage />} />
            <Route path="segregation" element={<OpSegregationPage />} />
            <Route path="sorting" element={<OpSortingPage />} />
            <Route path="storage" element={<OpStoragePage />} />
            <Route path="compost" element={<OpCompostPage />} />
            <Route path="outgoing" element={<OpOutgoingPage />} />
            <Route path="alerts" element={<OpAlertsPage />} />
            <Route path="history" element={<OpHistoryPage />} />
            <Route path="profile" element={<OpProfilePage />} />
            <Route path="more" element={<OpMorePage />} />
          </Route>
          <Route path="/staff" element={<RequireRole role="staff"><StaffLayout /></RequireRole>}>
            <Route index element={<StaffOverviewPage />} />
            <Route path="records" element={<StaffRecordsPage />} />
            <Route path="reports" element={<StaffReportsPage />} />
            <Route path="notifications" element={<StaffNotificationsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
