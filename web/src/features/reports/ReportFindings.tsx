import { useState } from 'react';
import { useNarrative, type Finding, type FindingTopic } from '../../api/reports';
import { btn } from '../../components/ui';

const QUESTIONS: [FindingTopic, string][] = [
  ['compare', 'How does this compare to last period?'],
  ['attention', 'What needs attention?'],
  ['next', 'What should we do next?'],
];

/** Findings computed from the report, the suggested questions that filter them, and the optional AI summary. */
export default function ReportFindings({ findings, narrative }: { findings: Finding[]; narrative: string }) {
  const [topic, setTopic] = useState<FindingTopic | null>(null);
  const [asked, setAsked] = useState(false);
  const ai = useNarrative(narrative, asked);
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
        <button className={`${btn.base} ${btn.small} ${btn.secondary}`} disabled={asked && ai.isFetching}
          onClick={() => (asked ? ai.refetch() : setAsked(true))}>
          {asked && ai.isFetching ? 'Writing summary…' : 'Explain this report'}
        </button>
      </div>
      {shown.length ? (
        <ul className="list-disc pl-5 text-sm">{shown.map((f) => <li key={f.text}>{f.text}</li>)}</ul>
      ) : <p className="text-sm text-muted">Nothing stands out for this period.</p>}
      {asked && !ai.isFetching && (
        <div aria-live="polite" className="rounded-lg bg-surface p-3 text-sm">
          {ai.data?.text ? (
            <>
              <p className="mb-1 text-xs font-semibold text-muted">AI summary, numbers checked against the report</p>
              <p>{ai.data.text}</p>
            </>
          ) : <p className="text-muted">The AI summary isn't available right now. The findings above are complete.</p>}
        </div>
      )}
    </section>
  );
}
