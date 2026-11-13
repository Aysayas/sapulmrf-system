import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Role, User } from './auth';
import { api } from './client';

export interface UserInput {
  name: string;
  username: string;
  role: Role;
  password?: string;
  active?: boolean;
}

export const useUsers = () => useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') });

export function useSaveUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<UserInput> & { id?: number }) =>
      id ? api<User>(`/users/${id}`, { method: 'PATCH', body }) : api<User>('/users', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
      qc.invalidateQueries({ queryKey: ['access'] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}

/** For a forgotten kiosk PIN. The admin never sees it; the operator sets a new one on their Profile. */
export function useClearKioskPin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/users/${id}/kiosk-pin`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}
