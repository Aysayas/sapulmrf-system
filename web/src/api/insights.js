import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const MODEL_LABEL = { ml: 'ML model (Ridge regression)', baseline: 'Baseline (7-day average)' };
export const usePredictions = (category) => useQuery({ queryKey: ['insights', 'predictions', category], queryFn: () => api(`/insights/predictions?category=${category}`), refetchInterval: 60_000 });
export const useFlags = () => useQuery({ queryKey: ['insights', 'flags'], queryFn: () => api('/insights/flags'), refetchInterval: 30_000 });
export function useDecideFlag() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, decision }) => api(`/insights/flags/${id}`, { method: 'POST', body: { decision } }),
        onSuccess: () => ['insights', 'approvals', 'activity'].forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
    });
}
