import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type Kind = 'categories' | 'puroks' | 'materials' | 'storage-areas';
export interface Item {
  id: number;
  name: string;
  active: boolean;
  capacity_kg: number | null;
  alert_pct: number | null;
}
export type ItemInput = Partial<Pick<Item, 'name' | 'active' | 'capacity_kg' | 'alert_pct'>>;

export const useItems = (kind: Kind) => useQuery({ queryKey: ['masterdata', kind], queryFn: () => api<Item[]>(`/masterdata/${kind}`) });

export function useSaveItem(kind: Kind) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: ItemInput & { id?: number }) =>
      id ? api<Item>(`/masterdata/${kind}/${id}`, { method: 'PATCH', body }) : api<Item>(`/masterdata/${kind}`, { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['masterdata', kind] });
      qc.invalidateQueries({ queryKey: ['activity'] });
    },
  });
}
