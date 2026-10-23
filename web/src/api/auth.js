import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';
export const ROLE_LABEL = {
    admin: 'Barangay Administrator',
    operator: 'MRF Operator',
    staff: 'Authorized Barangay Staff',
};
/** Where each role lands after login. Staff screens aren't built yet; RequireRole shows them a notice. */
export const HOME = { admin: '/admin', operator: '/op', staff: '/admin' };
/** The logged-in user, or null when there is no session. */
export function useMe() {
    return useQuery({
        queryKey: ['me'],
        queryFn: () => api('/auth/me').catch((e) => (e instanceof ApiError && e.status === 401 ? null : Promise.reject(e))),
        retry: false,
    });
}
export function useLogin() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body) => api('/auth/login', { method: 'POST', body }),
        onSuccess: (user) => qc.setQueryData(['me'], user),
    });
}
export function useLogout() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: () => api('/auth/logout', { method: 'POST' }),
        onSettled: () => {
            qc.clear();
            qc.setQueryData(['me'], null);
        },
    });
}
