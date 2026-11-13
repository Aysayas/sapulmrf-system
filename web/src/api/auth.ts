import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';

export type Role = 'admin' | 'operator' | 'staff';

export interface User {
  id: number;
  name: string;
  contact: string;
  username: string;
  role: Role;
  active: boolean;
  has_kiosk_pin: boolean;
  last_login_at: string | null;
  created_at: string;
}

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Barangay Administrator',
  operator: 'MRF Operator',
  staff: 'Authorized Barangay Staff',
};

/** Where each role lands after login. */
export const HOME: Record<Role, string> = { admin: '/admin', operator: '/op', staff: '/staff' };

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

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; contact?: string }) => api<User>('/auth/me', { method: 'PATCH', body }),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user);
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}

/** A wrong current password comes back as a 400 whose detail is the message to show. Other browsers get signed out. */
export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) => api<void>('/auth/me/password', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['activity'] }),
  });
}

/** Operators sign in at the resident kiosk by tapping their name and typing this PIN. */
export function useKioskPin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pin: string | null) =>
      pin ? api<void>('/auth/me/kiosk-pin', { method: 'PUT', body: { pin } }) : api<void>('/auth/me/kiosk-pin', { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}
