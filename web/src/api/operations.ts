import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Outgoing } from './approvals';
import { api, once } from './client';

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
  compliance_week_pct: number | null;
  in_storage_kg: number;
  active_batches: number;
  intake_14d: { day: string; kg: number }[];
  areas: AreaFill[];
  compost: BatchLive[];
  devices: { code: string; type: string; status: 'online' | 'offline' | 'never'; last_reading: Record<string, number | boolean | string> | null }[];
  latest_classification: Classification | null;
  pending_approvals: number;
  income_month: number;
  open_alerts: Partial<Record<'compost' | 'device' | 'storage', number>>;
  alert_batch_ids: number[];
}
export interface OutgoingView {
  income_month: number;
  sold_kg_month: number;
  compost_kg_month: number;
  disposed_kg_month: number;
  pending: number;
  compost_on_hand_kg: number;
  income_6m: { month: string; income: number }[];
  records: Outgoing[];
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
export const useCompost = (batch?: string, days?: number) =>
  useQuery({ queryKey: ['ops', 'compost', batch, days], queryFn: () => api<CompostView>(`/operations/compost?${qs({ batch, days })}`), ...LIVE });
export const useOutgoing = (days: number) =>
  useQuery({ queryKey: ['ops', 'outgoing', days], queryFn: () => api<OutgoingView>(`/operations/outgoing?days=${days}`), ...LIVE });
export const useCamera =() => useQuery({ queryKey: ['ops', 'camera'], queryFn: () => api<CameraView>('/operations/camera'), refetchInterval: 10_000 });
export const useWaiting = (waiting: 'segregation' | 'sorting') =>
  useQuery({ queryKey: ['ops', 'intake', 'waiting', waiting], queryFn: () => api<Delivery[]>(`/operations/intake?${qs({ waiting, limit: 200 })}`), ...LIVE });
export const usePendingClassifications = () =>
  useQuery({ queryKey: ['ops', 'classifications'], queryFn: () => api<Classification[]>('/classifications/pending'), refetchInterval: 10_000 });

export interface DeliveryIn {
  source_area_id: number;
  category_id: number;
  weight_kg: number;
  weighed_by: 'scale' | 'manual';
  scale_kg?: number;
  correction_reason?: string;
}
export interface SegregationIn { condition: 'segregated' | 'mixed'; wet_kg: number; dry_kg: number; note?: string }
/** material_id null means residual. */
export interface SortRow { material_id: number | null; bags: number; kg: number; storage_area_id: number }
/** Leave out final_material_id to accept the suggestion as it is. */
export interface ConfirmIn { final_material_id?: number | null; not_recyclable?: boolean; reason?: string }
/** material_id null means residual. */
export interface TransferIn { material_id: number | null; from_area_id: number; to_area_id: number; kg: number; bags: number | null }
export interface TransferOut { material: string; from_area: string; to_area: string; kg: number; bags: number; from_area_kg: number; to_area_kg: number }
export type Batch = Omit<BatchLive, 'temp_c' | 'moisture_pct' | 'read_at' | 'in_range' | 'day'>;
/** Set finished_kg to mark the batch finished. */
export interface BatchActivityIn { type: 'turning' | 'watering' | 'inspection'; note?: string; finished_kg?: number }

/** A write changes lists, totals, alerts and the log, so it refreshes all of them. */
function useWrite<In, Out>(request: (body: In) => Promise<Out>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => ['ops', 'overview', 'alerts', 'activity'].forEach(async (k) => {
      // Invalidating alone joins a first load already in flight, whose answer can predate this write.
      await qc.cancelQueries({ queryKey: [k] });
      qc.invalidateQueries({ queryKey: [k] });
    }),
  });
}
const post = <Out,>(path: string, body: unknown) => api<Out>(path, { method: 'POST', body });

export const useRecordDelivery = () => useWrite((b: DeliveryIn) => once('/deliveries', b, (keyed) => post<Delivery>('/deliveries', keyed)));
export const useRecordSegregation = () =>
  useWrite(({ deliveryId, ...b }: SegregationIn & { deliveryId: number }) => post<Delivery>(`/deliveries/${deliveryId}/segregation`, b));
export const useUndoSegregation = () =>
  useWrite((deliveryId: number) => api<Delivery>(`/deliveries/${deliveryId}/segregation`, { method: 'DELETE' }));
export const useSortDelivery = () => useWrite((b: { delivery_id: number; rows: SortRow[] }) => post<Delivery>('/sorting', b));
export const useConfirmClassification = () =>
  useWrite(({ id, ...b }: ConfirmIn & { id: number }) => post<Classification>(`/classifications/${id}/confirm`, b));
export const useTransfer = () => useWrite((b: TransferIn) => once('/inventory/transfers', b, (keyed) => post<TransferOut>('/inventory/transfers', keyed)));
export const useStartBatch = () => useWrite((b: { start_kg: number; sensor_id: number | null }) => post<Batch>('/compost/batches', b));
export const useLogBatchActivity = () =>
  useWrite(({ batchId, ...b }: BatchActivityIn & { batchId: number }) => post<Batch>(`/compost/batches/${batchId}/activities`, b));
