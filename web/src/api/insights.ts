import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

type Model = 'baseline' | 'ml';
export interface DayKg { day: string; kg: number }
export interface Predictions {
  ready: boolean;
  days_of_records: number;
  min_days: number;
  categories: { id: number; name: string }[];
  category: number;
  model_used: Model;
  errors_7d: Record<Model, number | null>;
  errors_14d: Record<Model, number | null>;
  history: DayKg[];
  forecast: DayKg[];
  made_on: string | null;
  compared: { day: string; predicted: number; actual: number; diff: number; pct: number | null }[];
  missing_days: number;
  avg_error_pct: number | null;
  outlook: { area: string; pct: number; kg: number; capacity_kg: number; alert_pct: number; per_day_kg: number; days_to_full: number | null; days_to_alert: number | null }[];
  schedule: { on: string; what: string; why: string }[];
  camera: Camera | null;
}
export interface Camera {
  confirmed: number; kept: number; kept_pct: number; changed: number; reviewed_wrong: number;
  by_material: { material: string; suggested: number; kept: number; changed: number; changed_to: string | null }[];
  by_confidence: { band: string; confirmed: number; kept_pct: number }[];
  kiosk: { with_camera: number; matched: number; matched_pct: number } | null;
}
export interface Flag {
  id: number;
  kind: 'weight' | 'gap';
  delivery_id: number;
  code: string;
  received_at: string;
  source_area: string;
  category: string;
  value_kg: number;
  expected_low: number;
  expected_high: number;
  why: string;
  expected: string;
  status: 'open' | 'valid' | 'incorrect';
  decided_by: string | null;
  decided_at: string | null;
}

export const MODEL_LABEL: Record<Model, string> = { ml: 'ML model (Ridge regression)', baseline: 'Baseline (7-day average)' };

export const usePredictions = (category: number) =>
  useQuery({ queryKey: ['insights', 'predictions', category], queryFn: () => api<Predictions>(`/insights/predictions?category=${category}`), refetchInterval: 60_000 });
export const useFlags = () => useQuery({ queryKey: ['insights', 'flags'], queryFn: () => api<Flag[]>('/insights/flags'), refetchInterval: 30_000 });

export function useDecideFlag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: 'valid' | 'incorrect' }) =>
      api<Flag>(`/insights/flags/${id}`, { method: 'POST', body: { decision } }),
    onSuccess: () => ['insights', 'approvals', 'activity'].forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
  });
}
