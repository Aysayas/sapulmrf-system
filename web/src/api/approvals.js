import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const OUTGOING_TYPE = { sale: 'Recyclable sale', compost: 'Compost given out', disposal: 'Residual for disposal' };
export const useApprovals = () => useQuery({ queryKey: ['approvals'], queryFn: () => api('/approvals'), refetchInterval: 30_000 });
export const useWeightReviews = () => useQuery({ queryKey: ['reviews', 'weights'], queryFn: () => api('/reviews/weights') });
export const useChangeReviews = () => useQuery({ queryKey: ['reviews', 'classifications'], queryFn: () => api('/reviews/classifications') });
function useRefresh() {
    const qc = useQueryClient();
    return () => ['approvals', 'reviews', 'ops', 'overview', 'activity'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}
export function useDecide() {
    const refresh = useRefresh();
    return useMutation({
        mutationFn: ({ kind, id, ...body }) => api(`/approvals/${kind}/${id}`, { method: 'POST', body }),
        onSuccess: refresh,
    });
}
export function useReview() {
    const refresh = useRefresh();
    return useMutation({
        mutationFn: ({ kind, id, review }) => api(`/reviews/${kind}/${id}`, { method: 'POST', body: { review } }),
        onSuccess: refresh,
    });
}
// ---- operator side ----
export const useMyAdjustments = () => useQuery({ queryKey: ['approvals', 'mine'], queryFn: () => api('/inventory/adjustments/mine'), refetchInterval: 30_000 });
export function useRequestAdjustment() {
    const refresh = useRefresh();
    return useMutation({
        mutationFn: (body) => api('/inventory/adjustments', { method: 'POST', body }),
        onSuccess: refresh,
    });
}
export function useRequestOutgoing() {
    const refresh = useRefresh();
    return useMutation({
        mutationFn: (body) => api('/outgoing', { method: 'POST', body }),
        onSuccess: refresh,
    });
}
