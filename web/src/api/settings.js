import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const useRanges = () => useQuery({ queryKey: ['settings'], queryFn: () => api('/settings') });
export function useSaveRanges() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body) => api('/settings', { method: 'PUT', body }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['settings'] });
            qc.invalidateQueries({ queryKey: ['masterdata', 'storage-areas'] });
            qc.invalidateQueries({ queryKey: ['activity'] });
        },
    });
}
