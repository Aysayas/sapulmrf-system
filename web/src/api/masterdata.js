import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const useItems = (kind) => useQuery({ queryKey: ['masterdata', kind], queryFn: () => api(`/masterdata/${kind}`) });
export function useSaveItem(kind) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, ...body }) => id ? api(`/masterdata/${kind}/${id}`, { method: 'PATCH', body }) : api(`/masterdata/${kind}`, { method: 'POST', body }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['masterdata', kind] });
            qc.invalidateQueries({ queryKey: ['activity'] });
        },
    });
}
