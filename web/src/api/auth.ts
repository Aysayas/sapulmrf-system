import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';

export type Role = 'admin' | 'operator' | 'staff';

export interface User {
  id: number;
  name: string;
  username: string;
  role: Role;
  active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Barangay Administrator',
  operator: 'MRF Operator',
  staff: 'Authorized Barangay Staff',
};

/** The logged-in user, or null when there is no session. */
export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => api<User>('/auth/me').catch((e) => (e instanceof ApiError && e.status === 401 ? null : Promise.reject(e))),
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { username: string; password: string }) => api<User>('/auth/login', { method: 'POST', body }),
    onSuccess: (user) => qc.setQueryData(['me'], user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>('/auth/logout', { method: 'POST' }),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(['me'], null);
    },
  });
}
