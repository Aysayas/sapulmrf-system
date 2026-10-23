import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
const LIVE = { refetchInterval: 30_000 };
export const useAlerts = (state) => useQuery({ queryKey: ['alerts', state], queryFn: () => api(`/alerts?state=${state}`), ...LIVE });
export const useAlertSummary = () => useQuery({ queryKey: ['alerts', 'summary'], queryFn: () => api('/alerts/summary'), ...LIVE });
export const useProblems = (status) => useQuery({ queryKey: ['alerts', 'problems', status], queryFn: () => api(`/problems?status=${status}`), ...LIVE });
function useRefresh() {
    const qc = useQueryClient();
    return () => ['alerts', 'overview', 'activity'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}
export function useAcknowledge() {
    const refresh = useRefresh();
    return useMutation({ mutationFn: (id) => api(`/alerts/${id}/acknowledge`, { method: 'POST' }), onSuccess: refresh });
}
export function useResolveProblem() {
    const refresh = useRefresh();
    return useMutation({
        mutationFn: ({ id, note }) => api(`/problems/${id}/resolve`, { method: 'POST', body: { note } }),
        onSuccess: refresh,
    });
}
// ---- operator side ----
export const useMyProblems = () => useQuery({ queryKey: ['alerts', 'problems', 'mine'], queryFn: () => api('/problems/mine'), ...LIVE });
export function useReportProblem() {
    const refresh = useRefresh();
    return useMutation({
        mutationFn: (body) => api('/problems', { method: 'POST', body }),
        onSuccess: refresh,
    });
}
