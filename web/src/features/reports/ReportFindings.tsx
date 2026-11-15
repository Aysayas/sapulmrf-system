import { useState } from 'react';
import { Link } from 'react-router';
import { type Finding, type FindingTopic } from '../../api/reports';
import { btn } from '../../components/ui';

const QUESTIONS: [FindingTopic, string][] = [
  ['compare', 'How does this compare to last period?'],
  ['attention', 'What needs attention?'],
  ['next', 'What should we do next?'],
];

/** Findings computed from the report, and the suggested questions that filter them. "Ask about this report" (admins)
 * opens Ask SapulMRF with this report already asked, for follow-up questions; no language model is involved. */
export default function ReportFindings({ findings, ask }: { findings: Finding[]; ask?: { text: string; topic: string } }) {
  const [topic, setTopic] = useState<FindingTopic | null>(null);
  if (!findings.length) return null;
  const shown = topic ? findings.filter((f) => f.topic === topic) : findings;

  return (
    <section aria-label="Findings" className="flex flex-col gap-3 rounded-xl border border-line bg-white p-4">
      <h2 className="font-bold">Findings</h2>
      <div role="group" aria-label="Suggested questions" className="flex flex-wrap gap-2">
        {QUESTIONS.map(([t, q]) => (
          <button key={t} aria-pressed={topic === t} onClick={() => setTopic(topic === t ? null : t)}
            className={`${btn.base} ${btn.small} ${topic === t ? btn.primary : btn.secondary}`}>{q}</button>
        ))}
        {ask && (
          <Link to={`/admin/assistant?${new URLSearchParams({ q: ask.text, topic: ask.topic })}`} className={`${btn.base} ${btn.small} ${btn.secondary}`}>
            Ask about this report →
          </Link>
        )}
      </div>
      {shown.length ? (
        <ul className="list-disc pl-5 text-sm">{shown.map((f) => <li key={f.text}>{f.text}</li>)}</ul>
      ) : <p className="text-sm text-muted">Nothing stands out for this period.</p>}
    </section>
  );
}
