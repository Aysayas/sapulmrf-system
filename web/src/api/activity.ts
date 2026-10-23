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

export type ActivityCategory = '' | 'logins' | 'users' | 'approvals' | 'reports' | 'records';
export interface ActivityFilters { userId?: number; days?: number; from?: string; to?: string; category?: ActivityCategory }

export function activityQuery(f: ActivityFilters) {
  const q = new URLSearchParams();
  if (f.userId) q.set('user_id', String(f.userId));
  if (f.days) q.set('days', String(f.days));
  if (f.from) q.set('from', f.from);
  if (f.to) q.set('to', f.to);
  if (f.category) q.set('category', f.category);
  return q;
}

export function useActivity(filters: ActivityFilters) {
  return useQuery({ queryKey: ['activity', filters], queryFn: () => api<Activity[]>(`/activity?${activityQuery(filters)}`) });
}
