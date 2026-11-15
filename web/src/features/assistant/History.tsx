import { useState } from 'react';
import { useDeleteConversation, useRename, type Conversation } from '../../api/assistant';
import { btn, inputCls } from '../../components/ui';
import { focus, Icon } from './icons';

function group(updated: string): string {
  const day = new Date(updated);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.floor((today.getTime() - new Date(day.getFullYear(), day.getMonth(), day.getDate()).getTime()) / 86_400_000);
  return days <= 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 7 ? 'Last 7 days' : 'Older';
}

function Row({ c, active, onOpen, onDeleted }: { c: Conversation; active: boolean; onOpen: () => void; onDeleted: () => void }) {
  const rename = useRename();
  const del = useDeleteConversation();
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [title, setTitle] = useState(c.title);

  if (editing)
    return (
      <form className="flex gap-1 px-1 py-1" onSubmit={(e) => { e.preventDefault(); if (title.trim()) rename.mutate({ id: c.id, title: title.trim() }, { onSuccess: () => setEditing(false) }); }}>
        <input aria-label="Chat name" className={`${inputCls} !py-1 text-xs`} value={title} maxLength={60} autoFocus
          onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === 'Escape' && setEditing(false)} />
        <button className={`${btn.base} ${btn.primary} ${btn.small}`}>Save</button>
      </form>
    );
  if (confirm)
    return (
      <div className="flex items-center gap-1.5 rounded-lg bg-crit-100 px-2 py-1.5 text-xs">
        <span className="min-w-0 flex-1 truncate text-crit">Delete “{c.title}”?</span>
        <button type="button" className="font-bold text-crit" onClick={() => del.mutate(c.id, { onSuccess: onDeleted })}>Delete</button>
        <button type="button" className="text-ink-2" onClick={() => setConfirm(false)}>Keep</button>
      </div>
    );
  return (
    <div className={`group flex items-center rounded-lg ${active ? 'bg-leaf-100' : 'hover:bg-surface'}`}>
      <button type="button" onClick={onOpen} aria-current={active ? 'page' : undefined}
        className={`${focus} min-w-0 flex-1 truncate px-2.5 py-1.5 text-left text-sm ${active ? 'font-bold text-leaf-900' : 'text-ink'}`}>
        {c.title}
      </button>
      <div className="flex shrink-0 gap-0.5 pr-1 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100">
        <button type="button" aria-label={`Rename ${c.title}`} className={`${focus} grid size-6 place-items-center rounded text-ink-2 hover:bg-white`} onClick={() => setEditing(true)}><Icon name="pencil" className="size-3.5" /></button>
        <button type="button" aria-label={`Delete ${c.title}`} className={`${focus} grid size-6 place-items-center rounded text-ink-2 hover:bg-white hover:text-crit`} onClick={() => setConfirm(true)}><Icon name="x" className="size-3.5" /></button>
      </div>
    </div>
  );
}

/** Past chats, newest first, grouped by when they were last used. */
export default function History({ items, current, onOpen, onNew }: {
  items: Conversation[]; current: number | null; onOpen: (id: number | null) => void; onNew: () => void;
}) {
  const groups = new Map<string, Conversation[]>();
  for (const c of items) groups.set(group(c.updated_at), [...(groups.get(group(c.updated_at)) ?? []), c]);
  return (
    <div className="flex h-full flex-col gap-3">
      <button type="button" onClick={onNew} className={`${btn.base} ${btn.primary} w-full`}>+ New chat</button>
      <nav aria-label="Past chats" className="-mx-1 flex-1 overflow-y-auto px-1">
        {items.length === 0 && <p className="px-2 text-xs text-muted">Your questions will be kept here.</p>}
        {[...groups].map(([label, cs]) => (
          <section key={label} className="mb-3">
            <h3 className="px-2.5 pb-1 text-[11px] font-semibold text-muted">{label}</h3>
            {cs.map((c) => <Row key={c.id} c={c} active={c.id === current} onOpen={() => onOpen(c.id)} onDeleted={() => c.id === current && onOpen(null)} />)}
          </section>
        ))}
      </nav>
    </div>
  );
}
