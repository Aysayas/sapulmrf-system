import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { ApiError } from '../api/client';
import LoginPage from '../features/auth/LoginPage';
import ComingSoon from '../features/placeholder/ComingSoon';
import SettingsLayout from '../features/settings/SettingsLayout';
import UsersPage from '../features/users/UsersPage';
import AdminLayout from '../layout/AdminLayout';
import RequireAdmin from './RequireAdmin';

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
          <Route path="/admin" element={<RequireAdmin><AdminLayout /></RequireAdmin>}>
            <Route index element={<ComingSoon title="MRF overview" phase={3} />} />
            <Route path="approvals" element={<ComingSoon title="Approvals" phase={4} />} />
            <Route path="operations" element={<ComingSoon title="Operations" phase={3} />} />
            <Route path="insights" element={<ComingSoon title="Insights" phase={6} />} />
            <Route path="settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="users" replace />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="roles" element={<ComingSoon title="Roles and permissions" phase={1} />} />
              <Route path="masterdata" element={<ComingSoon title="Master data" phase={2} />} />
              <Route path="devices" element={<ComingSoon title="IoT devices" phase={2} />} />
              <Route path="ranges" element={<ComingSoon title="Ranges and limits" phase={2} />} />
              <Route path="activity" element={<ComingSoon title="Activity log" phase={1} />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
