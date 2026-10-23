import { useEffect, useState, type ReactNode } from 'react';

/** Shared looks from the approved mockup (mockup.css), as Tailwind class strings and tiny components. */
export const btn = {
  base: 'inline-flex items-center justify-center gap-1.5 rounded-lg border px-3.5 py-1.5 text-sm font-semibold disabled:opacity-60',
  primary: 'border-leaf-700 bg-leaf-700 text-white hover:bg-leaf-800',
  secondary: 'border-edge bg-white text-leaf-900 hover:bg-surface',
  small: 'px-2.5 py-1 text-xs',
};
export const inputCls = 'w-full rounded-lg border border-edge bg-white px-3 py-2 text-sm outline-leaf-700 aria-[invalid=true]:border-crit';

const BADGE = { neutral: 'bg-surface-2 text-ink-2', ok: 'bg-leaf-100 text-leaf-700', warn: 'bg-warn-100 text-warn', crit: 'bg-crit-100 text-crit', dash: 'border border-dashed border-edge text-muted' };
export function Badge({ kind = 'neutral', children }: { kind?: keyof typeof BADGE; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2.5 text-[11px] leading-[18px] font-semibold whitespace-nowrap ${BADGE[kind]}`}>{children}</span>;
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="flex items-end gap-4">
      <div>
        <h1 className="text-2xl font-extrabold">{title}</h1>
        {sub && <p className="text-sm text-ink-2">{sub}</p>}
      </div>
      {actions && <div className="ml-auto flex gap-2">{actions}</div>}
    </div>
  );
}

/** Shows `message` for a few seconds at the bottom right. */
export function Toast({ message }: { message: string | null }) {
  const [shown, setShown] = useState(message);
  useEffect(() => {
    setShown(message);
    if (!message) return;
    const t = setTimeout(() => setShown(null), 3500);
    return () => clearTimeout(t);
  }, [message]);
  if (!shown) return null;
  return (
    <div role="status" className="fixed right-6 bottom-6 z-30 rounded-lg bg-leaf-900 px-4 py-3 text-sm text-white shadow-xl">
      ✓ {shown}
    </div>
  );
}

export function Drawer({ title, onClose, children, footer }: { title: string; onClose: () => void; children: ReactNode; footer: ReactNode }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);
  return (
    <>
      <div className="fixed inset-0 z-20 bg-leaf-900/35" onClick={onClose} />
      <aside role="dialog" aria-modal="true" aria-label={title} className="fixed inset-y-0 right-0 z-20 flex w-[460px] max-w-full flex-col gap-4 bg-white p-6 shadow-2xl">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold">{title}</h2>
          <button className={`${btn.base} ${btn.secondary} ${btn.small} ml-auto`} onClick={onClose}>
            Close ✕
          </button>
        </div>
        <div className="flex flex-1 flex-col gap-4 overflow-y-auto">{children}</div>
        <div className="flex justify-end gap-2 border-t border-line pt-4">{footer}</div>
      </aside>
    </>
  );
}
