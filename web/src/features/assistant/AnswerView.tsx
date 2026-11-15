import { useState } from 'react';
import { Link } from 'react-router';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { TOPICS, type Answer, type Chart, type Message } from '../../api/assistant';
import { useExportReport, type ReportFormat } from '../../api/reports';
import { btn } from '../../components/ui';
import { focus, Icon } from './icons';

const SERIES = ['#2e8b5e', '#8a5a22']; // leaf 600, then kraft for a second series (forecast)
const GRID = '#e7eee9';
const AXIS = { fontSize: 11, fill: '#5f6e66' };
const isDay = (s: string) => /^\d{4}-\d{2}-\d{2}$/.test(s);
const tick = (s: string) =>
  isDay(s) ? new Date(`${s}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' }) : s.length > 14 ? `${s.slice(0, 13)}…` : s;

function AnswerChart({ chart }: { chart: Chart }) {
  const data = chart.x.map((x, i) => Object.fromEntries([['x', x], ...chart.series.map((s) => [s.name, s.values[i]])]));
  const all = chart.series.flatMap((s) => s.values);
  const label = `${chart.kind === 'bar' ? 'Bar' : 'Line'} chart of ${chart.series.map((s) => s.name).join(' and ')}: ${chart.x.length} points, from ${Math.min(...all)} to ${Math.max(...all)}`;
  const common = (
    <>
      <CartesianGrid vertical={false} stroke={GRID} />
      <XAxis dataKey="x" tickFormatter={tick} tick={AXIS} axisLine={false} tickLine={false} minTickGap={12} interval="preserveStartEnd" />
      <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} tickFormatter={(v: number) => v.toLocaleString()} />
      <Tooltip labelFormatter={(l) => tick(String(l))} contentStyle={{ borderRadius: 8, border: '1px solid #d6e1da', fontSize: 12 }} />
      {chart.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
    </>
  );
  return (
    <div role="img" aria-label={label} className="h-[220px]">
      <ResponsiveContainer width="100%" height="100%">
        {chart.kind === 'bar' ? (
          <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            {common}
            {chart.series.map((s, i) => <Bar key={s.name} dataKey={s.name} fill={SERIES[i % 2]} radius={[4, 4, 0, 0]} isAnimationActive={false} />)}
          </BarChart>
        ) : (
          <LineChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            {common}
            {chart.series.map((s, i) => <Line key={s.name} dataKey={s.name} stroke={SERIES[i % 2]} strokeWidth={2} dot={false} isAnimationActive={false} />)}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function Exports({ a, asked }: { a: Answer; asked: boolean }) {
  const exp = useExportReport();
  const [err, setErr] = useState<string | null>(null);
  if (!a.export) return null;
  const go = (format: ReportFormat) =>
    exp.mutate({ format, kind: a.export!.kind, from: a.export!.from_day, to: a.export!.to_day, area: a.export!.area ?? 0 }, {
      onError: (e) => setErr(e.message),
    });
  return (
    <>
      <button type="button" className={`${btn.base} ${asked ? btn.primary : btn.secondary} ${btn.small}`} disabled={exp.isPending} onClick={() => go('csv')}>Download CSV</button>
      <button type="button" className={`${btn.base} ${asked ? btn.primary : btn.secondary} ${btn.small}`} disabled={exp.isPending} onClick={() => go('pdf')}>Download PDF</button>
      {err && <span role="alert" className="text-xs text-crit">{err}</span>}
    </>
  );
}

type Props = {
  message: Message;
  question: string;
  onAsk: (text: string, intent?: string) => void;
  onFeedback: (helpful: boolean, corrected?: string) => void;
  busy: boolean;
};

/** One answer, text first: what it found and the key numbers in words. A chart or table opens when the question
 * asked for it; otherwise it's offered under "Want to see it?", with the downloads. */
export default function AnswerView({ message, question, onAsk, onFeedback, busy }: Props) {
  const a = message.answer!;
  const [correcting, setCorrecting] = useState(false);
  const [open, setOpen] = useState(() => new Set<string>(a.show ?? []));
  const unsure = a.intent === 'unsure';
  const hasChart = !!a.chart && a.chart.x.length > 1;
  const offer = [hasChart && !open.has('chart') && 'chart', a.table && !open.has('table') && 'table'].filter(Boolean) as ('chart' | 'table')[];
  const when = new Date(message.created_at).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  return (
    <article className="flex max-w-3xl flex-col gap-3 rounded-2xl rounded-tl-sm bg-white p-4 ring-1 ring-line">
      <header className="flex items-baseline gap-3">
        <h2 className="text-base font-bold text-ink">{a.title}</h2>
        <time className="ml-auto shrink-0 text-[11px] text-muted" dateTime={message.created_at}>{when}</time>
      </header>
      <p className="text-sm leading-relaxed text-ink-2">{a.summary}</p>

      {a.cards.length > 0 && (
        <p className="text-sm leading-relaxed text-ink-2">
          {a.cards.map((c, i) => (
            <span key={c.label}>
              {i > 0 && <span className="text-muted"> · </span>}
              {c.label}: <strong className="font-bold text-ink">{c.value}</strong>{c.delta && ` (${c.delta})`}
            </span>
          ))}
        </p>
      )}

      {hasChart && open.has('chart') && <AnswerChart chart={a.chart!} />}

      {a.table && open.has('table') && (
        <div className="max-h-64 overflow-auto rounded-xl ring-1 ring-line">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-surface-2 text-ink-2">
              <tr>{a.table.columns.map((c) => <th key={c} scope="col" className="px-2.5 py-1.5 font-semibold whitespace-nowrap">{c}</th>)}</tr>
            </thead>
            <tbody>
              {a.table.rows.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  {r.map((v, j) => <td key={j} className={`px-2.5 py-1.5 ${typeof v === 'number' ? 'text-right' : ''}`}>{typeof v === 'number' ? v.toLocaleString() : v ?? '-'}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {a.steps?.length > 0 && (
        <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-2 marker:font-bold marker:text-leaf-700">
          {a.steps.map((s) => <li key={s}>{s}</li>)}
        </ol>
      )}
      {a.links?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {a.links.map((l) => (
            <Link key={l.to} to={l.to} className={`${btn.base} ${btn.primary} ${btn.small}`}>{l.label} →</Link>
          ))}
        </div>
      )}

      {a.note && <p className="text-xs text-muted">{a.note}</p>}

      {(offer.length > 0 || a.export) && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-2">{offer.length ? 'Want to see it?' : 'Keep a copy:'}</span>
          {offer.map((v) => (
            <button key={v} type="button" onClick={() => setOpen((o) => new Set([...o, v]))} className={`${btn.base} ${btn.secondary} ${btn.small}`}>
              {v === 'chart' ? (a.chart!.kind === 'line' ? 'Show the trend' : 'Show a chart') : 'Show the table'}
            </button>
          ))}
          <Exports a={a} asked={(a.show ?? []).includes('export')} />
        </div>
      )}

      {(a.suggestions.length > 0 || unsure) && (
        <div className="flex flex-wrap gap-1.5">
          {a.suggestions.map((s) => (
            <button key={s} type="button" disabled={busy} onClick={() => onAsk(s.replace(/^Not what you meant\? /, ''))}
              className={`${focus} rounded-full border border-leaf-300 bg-leaf-100/60 px-3 py-1 text-xs font-semibold text-leaf-800 hover:bg-leaf-100 disabled:opacity-60`}>
              {s}
            </button>
          ))}
        </div>
      )}

      {!unsure && (
        <footer className="flex flex-wrap items-center gap-1.5 border-t border-line pt-2 text-xs text-muted">
          <span>Was this what you asked?</span>
          <button type="button" aria-label="Yes, helpful" aria-pressed={message.helpful === true} onClick={() => { setCorrecting(false); onFeedback(true); }}
            className={`${focus} grid size-7 place-items-center rounded-md ${message.helpful === true ? 'bg-leaf-100 text-leaf-800' : 'text-ink-2 hover:bg-surface'}`}><Icon name="up" /></button>
          <button type="button" aria-label="No, I meant something else" aria-pressed={message.helpful === false} aria-expanded={correcting} onClick={() => setCorrecting((c) => !c)}
            className={`${focus} grid size-7 place-items-center rounded-md ${message.helpful === false ? 'bg-crit-100 text-crit' : 'text-ink-2 hover:bg-surface'}`}><Icon name="down" /></button>
          <button type="button" disabled={busy} onClick={() => onAsk(question, a.intent)} className={`${focus} ml-auto rounded font-semibold text-leaf-700 hover:underline disabled:opacity-60`}>
            Ask again
          </button>
          {correcting && (
            <div className="flex w-full flex-wrap items-center gap-1.5 pt-1.5">
              <span className="text-ink-2">I meant:</span>
              {TOPICS.filter(([k]) => k !== a.intent).map(([k, label]) => (
                <button key={k} type="button" disabled={busy}
                  onClick={() => { setCorrecting(false); onFeedback(false, k); onAsk(question, k); }}
                  className={`${focus} rounded-full border border-edge bg-white px-2.5 py-0.5 font-semibold text-ink-2 hover:bg-surface disabled:opacity-60`}>
                  {label}
                </button>
              ))}
            </div>
          )}
        </footer>
      )}
    </article>
  );
}
