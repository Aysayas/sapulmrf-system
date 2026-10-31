import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export interface Ranges {
  compost_temp_min: number;
  compost_temp_max: number;
  moisture_min: number;
  moisture_max: number;
  prediction_min_days: number;
  anomaly_limit: number;
}
export type RangesInput = Ranges & { storage_areas: { id: number; capacity_kg: number; alert_pct: number }[] };

export const useRanges = () => useQuery({ queryKey: ['settings'], queryFn: () => api<Ranges>('/settings') });

export function useSaveRanges() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RangesInput) => api<Ranges>('/settings', { method: 'PUT', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['masterdata', 'storage-areas'] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}
