import { useQuery } from '@tanstack/react-query';
import { api } from './client';
export function activityQuery(f) {
    const q = new URLSearchParams();
    if (f.userId)
        q.set('user_id', String(f.userId));
    if (f.days)
        q.set('days', String(f.days));
    if (f.from)
        q.set('from', f.from);
    if (f.to)
        q.set('to', f.to);
    if (f.category)
        q.set('category', f.category);
    return q;
}
export function useActivity(filters) {
    return useQuery({ queryKey: ['activity', filters], queryFn: () => api(`/activity?${activityQuery(filters)}`) });
}
