import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AreaFill } from '../api/operations';

// One series per chart, so one hue (leaf 600) and no legend; the card title names the series (dataviz skill).
const SERIES = '#2e8b5e';
const GRID = '#e7eee9';
const AXIS = { fontSize: 11, fill: '#5f6e66' };

const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', day: 'numeric' });
const time = (iso: string) => new Date(iso).toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' });

/** What a chart shows, for screen readers. */
const span = (values: number[], unit: string) =>
  values.length ? `${values.length} points, from ${Math.min(...values)} to ${Math.max(...values)} ${unit}` : 'no data yet';

function TipBox({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-line">
      <div className="text-muted">{title}</div>
      <div className="font-bold text-ink">{value}</div>
    </div>
  );
}

/** Daily kg received, last 14 days. */
export function IntakeChart({ data, height = 220 }: { data: { day: string; kg: number }[]; height?: number }) {
  return (
    <div role="img" aria-label={`Bar chart of kg received per day: ${span(data.map((d) => d.kg), 'kg')}`}>
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="day" tickFormatter={day} tick={AXIS} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={18} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} width={36} />
        <Tooltip cursor={{ fill: '#ddefe3', opacity: 0.6 }} content={({ active, payload }) =>
          active && payload?.[0] ? <TipBox title={day(String(payload[0].payload.day))} value={`${payload[0].value} kg received`} /> : null} />
        <Bar dataKey="kg" fill={SERIES} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
    </div>
  );
}

/** Daily kg: actual days solid, forecast days hatched in the same hue (one series, two states; the key says which). */
export function ForecastChart({ actual, forecast, height = 240 }: { actual: { day: string; kg: number }[]; forecast: { day: string; kg: number }[]; height?: number }) {
  const data = [...actual.map((d) => ({ ...d, predicted: false })), ...forecast.map((d) => ({ ...d, predicted: true }))];
  return (
    <div role="img" aria-label={`Line chart of kg received and forecast per day: ${span([...actual, ...forecast].map((d) => d.kg), 'kg')}`}>
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }} barCategoryGap={2}>
        <defs>
          <pattern id="forecast-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="#ddefe3" />
            <line x1="0" y1="0" x2="0" y2="6" stroke={SERIES} strokeWidth="3" />
          </pattern>
        </defs>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="day" tickFormatter={day} tick={AXIS} axisLine={false} tickLine={false} minTickGap={18} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} width={36} />
        <Tooltip cursor={{ fill: '#ddefe3', opacity: 0.6 }} content={({ active, payload }) =>
          active && payload?.[0] ? (
            <TipBox title={day(String(payload[0].payload.day))}
              value={`${payload[0].value} kg ${payload[0].payload.predicted ? 'predicted' : 'received'}`} />
          ) : null} />
        <Bar dataKey="kg" radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {data.map((d) => (
            <Cell key={d.day} fill={d.predicted ? 'url(#forecast-hatch)' : SERIES} stroke={d.predicted ? SERIES : undefined} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
    </div>
  );
}

/** Income from approved sales per month. */
export function IncomeChart({ data, height = 220 }: { data: { month: string; income: number }[]; height?: number }) {
  const month = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-PH', { month: 'short', year: 'numeric' });
  const peso = (n: number) => `₱${n.toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return (
    <div role="img" aria-label={`Bar chart of income per month: ${span(data.map((d) => d.income), 'pesos')}`}>
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }} barCategoryGap={8}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="month" tickFormatter={month} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} width={52} tickFormatter={(v: number) => `₱${v.toLocaleString()}`} />
        <Tooltip cursor={{ fill: '#ddefe3', opacity: 0.6 }} content={({ active, payload }) =>
          active && payload?.[0] ? <TipBox title={month(String(payload[0].payload.month))} value={`${peso(Number(payload[0].value))} income`} /> : null} />
        <Bar dataKey="income" fill={SERIES} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
    </div>
  );
}

/** One compost reading over time, with the configured range shaded. */
export function ReadingChart({ data, field, unit, min, max, height = 200 }: {
  data: { at: string; temp_c: number; moisture_pct: number }[]; field: 'temp_c' | 'moisture_pct'; unit: string; min: number; max: number; height?: number;
}) {
  const values = data.map((d) => d[field]);
  const lo = Math.floor(Math.min(min, ...values) - 3);
  const hi = Math.ceil(Math.max(max, ...values) + 3);
  return (
    <div role="img" aria-label={`Line chart of readings over time: ${span(values, unit)}`}>
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <ReferenceArea y1={min} y2={max} fill="#ddefe3" fillOpacity={0.6} ifOverflow="extendDomain"
          label={{ value: `range ${min}–${max}${unit}`, position: 'insideBottomRight', fontSize: 10, fill: '#1d6b47' }} />
        <XAxis dataKey="at" tickFormatter={time} tick={AXIS} axisLine={false} tickLine={false} minTickGap={40} />
        <YAxis domain={[lo, hi]} tick={AXIS} axisLine={false} tickLine={false} width={44} unit={unit} />
        <Tooltip content={({ active, payload }) =>
          active && payload?.[0] ? <TipBox title={time(String(payload[0].payload.at))} value={`${payload[0].value}${unit}`} /> : null} />
        <Line dataKey={field} stroke={SERIES} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
    </div>
  );
}

/** A storage area's fill. Colour shows state (warn at the alert level) and the words say it too. */
export function FillBar({ area }: { area: AreaFill }) {
  const full = area.pct >= area.alert_pct;
  return (
    <div className="py-1.5">
      {/* wraps instead of cutting the name: "Demo Area B · Paper & cardboard" is what tells areas apart */}
      <div className="flex flex-wrap justify-between gap-x-2 text-sm">
        <span>{area.name}</span>
        <span className={`whitespace-nowrap ${full ? 'font-bold text-warn' : 'text-ink-2'}`}>
          {area.pct}% · {Math.round(area.kg).toLocaleString()} / {area.capacity_kg.toLocaleString()} kg{full ? ' · almost full' : ''}
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={area.pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${area.name} fill`}>
        <div className={`h-full rounded-full ${full ? 'bg-warn' : 'bg-leaf-600'}`} style={{ width: `${Math.min(100, area.pct)}%` }} />
      </div>
    </div>
  );
}

export function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <div className="text-xs font-semibold text-ink-2">{label}</div>
      <div className="mt-1 text-[28px] leading-tight font-extrabold">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}
