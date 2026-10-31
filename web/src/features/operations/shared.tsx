import type { ReactNode } from 'react';

export const when = (iso: string) =>
  new Date(iso).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
export const kg = (n: number) => `${(Math.round(n * 10) / 10).toLocaleString()} kg`;
export const peso = (n: number) => `₱${n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function Period<T extends number | string | undefined>({ value, options, onChange }: { value: T; options: readonly (readonly [string, T])[]; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label="Period" className="inline-flex shrink-0 self-start overflow-hidden rounded-lg border border-leaf-700 whitespace-nowrap">
      {options.map(([label, d]) => (
        <button
          key={label}
          aria-pressed={value === d}
          onClick={() => onChange(d)}
          className={`border-r border-leaf-700 px-3.5 py-1.5 text-sm font-semibold last:border-r-0 ${value === d ? 'bg-leaf-700 text-white' : 'text-leaf-700'}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** The bordered table used across Operations, with loading, error and empty rows. */
export function Table({ label, head, state, empty, children }: {
  label: string; head: string[]; state: { isPending: boolean; error: Error | null; count?: number }; empty: string; children: ReactNode;
}) {
  const row = (text: string, cls: string) => <tr><td colSpan={head.length} className={`px-3 py-4 ${cls}`}>{text}</td></tr>;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white">
      <table aria-label={label} className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            {head.map((h) => <th key={h} className="px-3 py-2 font-semibold whitespace-nowrap">{h}</th>)}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-line/60 [&>tr:last-child]:border-0 [&_td]:px-3 [&_td]:py-2.5">
          {state.isPending && row('Loading…', 'text-muted')}
          {state.error && row(state.error.message, 'text-crit')}
          {state.count === 0 && row(empty, 'text-muted')}
          {children}
        </tbody>
      </table>
    </div>
  );
}

/** A plain percentage bar for one row (compliance by purok). */
export function PctBar({ pct, label }: { pct: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-40 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className="h-full rounded-full bg-leaf-600" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right font-semibold">{pct}%</span>
    </div>
  );
}
