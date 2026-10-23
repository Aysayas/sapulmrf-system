import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export interface Activity {
  id: number;
  at: string;
  user_id: number | null;
  who: string;
  action: string;
  record: string;
}

export function useActivity(filters: { userId?: number; days?: number }) {
  const q = new URLSearchParams();
  if (filters.userId) q.set('user_id', String(filters.userId));
  if (filters.days) q.set('days', String(filters.days));
  return useQuery({ queryKey: ['activity', filters], queryFn: () => api<Activity[]>(`/activity?${q}`) });
}
