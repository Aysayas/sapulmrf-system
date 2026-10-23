import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, download } from './client';
const query = (p) => {
    const q = new URLSearchParams({ from: p.from, to: p.to });
    if (p.area)
        q.set('area', String(p.area));
    return q;
};
export const useReport = (p) => useQuery({ queryKey: ['report', p], queryFn: () => api(`/reports/${p.kind}?${query(p)}`), enabled: !!p });
export const useRecentReports = () => useQuery({ queryKey: ['reports-recent'], queryFn: () => api('/reports/recent') });
export function useExportReport() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ format, ...p }) => {
            const q = query(p);
            q.set('format', format);
            return download(`/reports/${p.kind}/export?${q}`);
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['reports-recent'] });
            qc.invalidateQueries({ queryKey: ['activity'] });
        },
    });
}
