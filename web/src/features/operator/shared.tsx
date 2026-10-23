import type { ReactNode } from 'react';
import { Badge } from '../../components/ui';

const STATUS = {
  pending: ['warn', 'Pending approval'],
  approved: ['ok', 'Approved'],
  rejected: ['crit', 'Rejected'],
  open: ['warn', 'Open'],
  resolved: ['ok', 'Resolved'],
} as const;

export function StatusBadge({ status }: { status: keyof typeof STATUS }) {
  const [kind, label] = STATUS[status];
  return <Badge kind={kind}>{label}</Badge>;
}

/** A labelled form field with its error under it. */
export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {label}
      {children}
      {error && <span className="text-xs font-normal text-crit">{error}</span>}
    </label>
  );
}

/** One card in a phone list. */
export function Card({ children, label }: { children: ReactNode; label?: string }) {
  return <li aria-label={label} className="rounded-xl border border-line bg-white p-3">{children}</li>;
}

export const touch = 'min-h-11';
