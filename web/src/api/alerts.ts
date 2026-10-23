import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export interface Alert {
  id: number;
  kind: 'compost' | 'device' | 'storage';
  title: string;
  details: string;
  opened_at: string;
  resolved_at: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
}
export interface Problem {
  id: number;
  code: string;
  kind: 'device' | 'record';
  device: string | null;
  record_ref: string;
  details: string;
  reported_by: string | null;
  reported_at: string;
  status: 'open' | 'resolved';
  resolved_by: string | null;
  resolved_at: string | null;
  note: string;
}
export interface AlertSummary {
  open_alerts: number;
  by_kind: Partial<Record<Alert['kind'], number>>;
  unacknowledged: number;
  open_reports: number;
  latest: { type: 'alert' | 'report'; id: number; title: string; details: string; at: string }[];
}

const LIVE = { refetchInterval: 30_000 };

export const useAlerts = (state: 'open' | 'acknowledged' | 'resolved') =>
  useQuery({ queryKey: ['alerts', state], queryFn: () => api<Alert[]>(`/alerts?state=${state}`), ...LIVE });
export const useAlertSummary = () => useQuery({ queryKey: ['alerts', 'summary'], queryFn: () => api<AlertSummary>('/alerts/summary'), ...LIVE });
export const useProblems = (status: 'open' | 'resolved') =>
  useQuery({ queryKey: ['alerts', 'problems', status], queryFn: () => api<Problem[]>(`/problems?status=${status}`), ...LIVE });

function useRefresh() {
  const qc = useQueryClient();
  return () => ['alerts', 'overview', 'activity'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

export function useAcknowledge() {
  const refresh = useRefresh();
  return useMutation({ mutationFn: (id: number) => api<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }), onSuccess: refresh });
}

export function useResolveProblem() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, note }: { id: number; note: string }) => api<Problem>(`/problems/${id}/resolve`, { method: 'POST', body: { note } }),
    onSuccess: refresh,
  });
}
