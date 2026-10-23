import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { Classification, Delivery } from './operations';

interface Decided {
  status: 'pending' | 'approved' | 'rejected';
  requested_by: string | null;
  decided_by: string | null;
  decided_at: string | null;
  comment: string;
}
export interface Adjustment extends Decided {
  id: number;
  requested_at: string;
  material: string;
  area: string;
  system_kg: number;
  actual_kg: number;
  reason: string;
  details: string;
  current_kg: number;
  area_kg: number;
  area_after_kg: number;
  capacity_kg: number;
}
export interface Outgoing extends Decided {
  id: number;
  code: string;
  requested_at: string;
  type: 'sale' | 'compost' | 'disposal';
  material: string;
  area: string | null;
  kg: number;
  recipient: string;
  price_per_kg: number | null;
  total: number | null;
  available_kg: number;
  area_kg: number | null;
  area_after_kg: number | null;
  capacity_kg: number | null;
}
export type Counts = { adjustments: number; outgoing: number; weights: number; classifications: number; flagged: number };
export interface Approvals {
  counts: Counts;
  adjustments: Adjustment[];
  outgoing: Outgoing[];
}

export const OUTGOING_TYPE = { sale: 'Recyclable sale', compost: 'Compost given out', disposal: 'Residual for disposal' } as const;

export const useApprovals = () => useQuery({ queryKey: ['approvals'], queryFn: () => api<Approvals>('/approvals'), refetchInterval: 30_000 });
export const useWeightReviews = () => useQuery({ queryKey: ['reviews', 'weights'], queryFn: () => api<Delivery[]>('/reviews/weights') });
export const useChangeReviews = () =>
  useQuery({ queryKey: ['reviews', 'classifications'], queryFn: () => api<Classification[]>('/reviews/classifications') });

function useRefresh() {
  const qc = useQueryClient();
  return () => ['approvals', 'reviews', 'ops', 'overview', 'activity'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

export function useDecide() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ kind, id, ...body }: { kind: 'adjustments' | 'outgoing'; id: number; decision: 'approve' | 'reject'; comment: string }) =>
      api<Adjustment | Outgoing>(`/approvals/${kind}/${id}`, { method: 'POST', body }),
    onSuccess: refresh,
  });
}

export function useReview() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ kind, id, review }: { kind: 'weights' | 'classifications'; id: number; review: 'ok' | 'recheck' | 'wrong' }) =>
      api(`/reviews/${kind}/${id}`, { method: 'POST', body: { review } }),
    onSuccess: refresh,
  });
}
