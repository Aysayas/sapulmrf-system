import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
export const useUsers = () => useQuery({ queryKey: ['users'], queryFn: () => api('/users') });
export function useSaveUser() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ id, ...body }) => id ? api(`/users/${id}`, { method: 'PATCH', body }) : api('/users', { method: 'POST', body }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['users'] });
            qc.invalidateQueries({ queryKey: ['access'] });
            qc.invalidateQueries({ queryKey: ['activity'] });
        },
    });
}
