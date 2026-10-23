import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export interface Delivery {
  id: number;
  code: string;
  received_at: string;
  source_area: string;
  category: string;
  weight_kg: number;
  weighed_by: 'scale' | 'manual';
  scale_kg: number | null;
  corrected: boolean;
  correction_reason: string | null;
  status: 'awaiting' | 'separated' | 'sorted';
  recorded_by: string | null;
  segregation: { condition: 'segregated' | 'mixed'; wet_kg: number; dry_kg: number; note: string; checked_at: string } | null;
}
export interface Classification {
  id: number;
  suggested_at: string;
  suggested: string;
  confidence: number;
  model_version: string;
  image_url: string;
  final: string | null;
  changed: boolean | null;
  reason: string;
  confirmed_by: string | null;
  confirmed_at: string | null;
}
export interface AreaFill { id: number; name: string; capacity_kg: number; alert_pct: number; kg: number; pct: number }
export interface BatchLive {
  id: number;
  code: string;
  started_at: string;
  start_kg: number;
  sensor: string | null;
  finished_at: string | null;
  produced_kg: number | null;
  activities: { type: string; note: string; by: string | null; at: string }[];
  temp_c: number | null;
  moisture_pct: number | null;
  read_at: string | null;
  in_range: boolean | null;
  day: number;
}
export interface Overview {
  today_deliveries: number;
  today_kg: number;
  awaiting_segregation: number;
  compliance_week_pct: number;
  in_storage_kg: number;
  active_batches: number;
  intake_14d: { day: string; kg: number }[];
  areas: AreaFill[];
  compost: BatchLive[];
  devices: { code: string; type: string; status: 'online' | 'offline' | 'never'; last_reading: Record<string, number | boolean | string> | null }[];
  latest_classification: Classification | null;
}
export interface Compliance {
  days: number;
  deliveries: number;
  segregated: number;
  pct: number;
  wet_kg_separated: number;
  rows: { source_area: string; deliveries: number; segregated: number; pct: number }[];
}
export interface SortingView {
  classified: number;
  unchanged: number;
  changed: number;
  accepted_pct: number;
  pending: number;
  sorted_kg: number;
  classifications: Classification[];
  sorted: { at: string; delivery: string | null; material: string; bags: number; kg: number; area: string }[];
}
export interface InventoryView {
  areas: AreaFill[];
  stock: { material: string; area: string; bags: number; kg: number; last_change: string }[];
}
export interface CompostView {
  ranges: { compost_temp_min: number; compost_temp_max: number; moisture_min: number; moisture_max: number };
  batches: BatchLive[];
  selected: string | null;
  series: { at: string; temp_c: number; moisture_pct: number }[];
}
export interface CameraView {
  latest: Classification | null;
  pending: number;
  today: number;
  accepted_pct: number;
  bins: { material: string; kg: number; bags: number }[];
}

const LIVE = { refetchInterval: 30_000 };
const qs = (o: Record<string, string | number | undefined>) =>
  new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)])).toString();

export const useOverview = () => useQuery({ queryKey: ['overview'], queryFn: () => api<Overview>('/overview'), ...LIVE });
export const useIntake = (days?: number, q?: string) =>
  useQuery({ queryKey: ['ops', 'intake', days, q], queryFn: () => api<Delivery[]>(`/operations/intake?${qs({ days, q, limit: 100 })}`), ...LIVE });
export const useCompliance = (days: number) =>
  useQuery({ queryKey: ['ops', 'segregation', days], queryFn: () => api<Compliance>(`/operations/segregation?days=${days}`), ...LIVE });
export const useSorting = (days: number) =>
  useQuery({ queryKey: ['ops', 'sorting', days], queryFn: () => api<SortingView>(`/operations/sorting?days=${days}`), ...LIVE });
export const useInventory = () => useQuery({ queryKey: ['ops', 'inventory'], queryFn: () => api<InventoryView>('/operations/inventory'), ...LIVE });
export const useCompost = (batch?: string) =>
  useQuery({ queryKey: ['ops', 'compost', batch], queryFn: () => api<CompostView>(`/operations/compost?${qs({ batch })}`), ...LIVE });
export const useCamera = () => useQuery({ queryKey: ['ops', 'camera'], queryFn: () => api<CameraView>('/operations/camera'), refetchInterval: 10_000 });
