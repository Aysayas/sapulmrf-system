import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, download } from './client';

export type ReportKind = 'intake' | 'segregation' | 'inventory' | 'composting' | 'outgoing' | 'income';
export type ReportFormat = 'pdf' | 'csv';
export interface ReportParams { kind: ReportKind; from: string; to: string; area: number }

export interface Report {
  kind: ReportKind;
  title: string;
  subtitle: string;
  summary: [string, string][];
  columns: string[];
  rows: (string | number)[][];
  total_rows: number;
}
export interface RecentExport {
  id: number;
  kind: ReportKind;
  title: string;
  from_day: string;
  to_day: string;
  area_id: number | null;
  area: string;
  format: ReportFormat;
  by: string;
  created_at: string;
}

const query = (p: Omit<ReportParams, 'kind'>) => {
  const q = new URLSearchParams({ from: p.from, to: p.to });
  if (p.area) q.set('area', String(p.area));
  return q;
};

export const useReport = (p: ReportParams | null) =>
  useQuery({ queryKey: ['report', p], queryFn: () => api<Report>(`/reports/${p!.kind}?${query(p!)}`), enabled: !!p });

export const useRecentReports = () => useQuery({ queryKey: ['reports-recent'], queryFn: () => api<RecentExport[]>('/reports/recent') });

/** One past export, re-read without logging a new export. Open to admins and staff with the reports grant. */
export const useExportView = (id: number | null) =>
  useQuery({ queryKey: ['report-export', id], queryFn: () => api<Report>(`/reports/exports/${id}`), enabled: id !== null });
export const downloadExport = (id: number) => download(`/reports/exports/${id}/download`);

export function useExportReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ format, ...p }: ReportParams & { format: ReportFormat }) => {
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
