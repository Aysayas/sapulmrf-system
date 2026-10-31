import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type Screen = 'segregation' | 'predictions' | 'alerts' | 'camera' | 'reports';
export interface StaffAccess {
  user_id: number;
  name: string;
  username: string;
  active: boolean;
  grants: Record<Screen, boolean>;
}
export interface AccessOverview {
  screens: { key: Screen; label: string }[];
  staff: StaffAccess[];
}

export const useAccess = () => useQuery({ queryKey: ['access'], queryFn: () => api<AccessOverview>('/access') });

/** A staff member's own grants, for hiding tabs. The API still enforces them. */
export const useMyAccess = () => useQuery({ queryKey: ['access', 'me'], queryFn: () => api<StaffAccess>('/access/me') });

export function useSaveAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (changes: { userId: number; grants: Partial<Record<Screen, boolean>> }[]) =>
      Promise.all(changes.map((c) => api<StaffAccess>(`/access/${c.userId}`, { method: 'PUT', body: { grants: c.grants } }))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['access'] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}
