import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const useAccess = () => useQuery({ queryKey: ['access'], queryFn: () => api('/access') });
export function useSaveAccess() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (changes) => Promise.all(changes.map((c) => api(`/access/${c.userId}`, { method: 'PUT', body: { grants: c.grants } }))),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['access'] });
            qc.invalidateQueries({ queryKey: ['activity'] });
        },
    });
}
