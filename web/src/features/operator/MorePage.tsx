import { Link } from 'react-router';
import { useAlertSummary } from '../../api/alerts';

const LINKS = [
  ['/op/segregation', 'Segregation'],
  ['/op/compost', 'Compost'],
  ['/op/outgoing', 'Outgoing'],
  ['/op/alerts', 'Alerts'],
  ['/op/history', 'History'],
  ['/op/profile', 'Profile'],
] as const;

/** The screens that don't fit in the bottom tabs. */
export default function MorePage() {
  const alerts = useAlertSummary().data?.unacknowledged ?? 0;
  return (
    <>
      <h1 className="text-2xl font-extrabold">More</h1>
      <nav aria-label="More screens" className="flex flex-col divide-y divide-line rounded-xl border border-line bg-white">
        {LINKS.map(([to, label]) => (
          <Link key={to} to={to} className="flex min-h-14 items-center justify-between px-4 font-semibold">
            {label}
            {label === 'Alerts' && alerts > 0 && (
              <span className="rounded-full bg-crit px-2 text-xs font-bold text-white" aria-label={`${alerts} not acknowledged`}>{alerts}</span>
            )}
          </Link>
        ))}
      </nav>
    </>
  );
}
