import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { ApiError } from '../api/client';
import LoginPage from '../features/auth/LoginPage';
import ComingSoon from '../features/placeholder/ComingSoon';
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
            <Route path="settings" element={<Navigate to="/admin/settings/users" replace />} />
            <Route path="settings/:tab" element={<ComingSoon title="Settings" phase={1} />} />
          </Route>
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
