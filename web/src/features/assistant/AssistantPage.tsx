import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useAsk, useConversation, useConversations, useFeedback, useSuggestions } from '../../api/assistant';
import { btn, Drawer } from '../../components/ui';
import AnswerView from './AnswerView';
import History from './History';
import { focus, Icon } from './icons';

/** Ask SapulMRF: questions about the MRF's own data, answered from the same numbers as Reports and Insights. */
export default function AssistantPage() {
  const [params, setParams] = useSearchParams();
  const current = params.get('c') ? Number(params.get('c')) : null;
  const open = (id: number | null) => setParams(id ? { c: String(id) } : {});

  const list = useConversations();
  const chat = useConversation(current);
  const suggestions = useSuggestions().data ?? [];
  const ask = useAsk();
  const feedback = useFeedback();
  const [text, setText] = useState('');
  const [pending, setPending] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const box = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);

  const messages = chat.data?.messages ?? [];
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' }); // newer Chrome returns a promise here: never hand it back to React
  }, [messages.length, pending]);

  const send = (question: string, intent?: string) => {
    const q = question.trim();
    if (!q || ask.isPending) return;
    setPending(q);
    setText('');
    ask.mutate({ text: q, conversation_id: current, intent }, {
      onSuccess: (out) => { if (out.conversation_id !== current) open(out.conversation_id); },
      onError: () => setText(q), // keep the question so it can be sent again
      onSettled: () => { setPending(null); box.current?.focus(); },
    });
  };

  const history = (
    <History items={list.data ?? []} current={current} onOpen={(id) => { open(id); setDrawer(false); }}
      onNew={() => { open(null); setDrawer(false); box.current?.focus(); }} />
  );
  const empty = current === null && !pending;

  return (
    <div className="-mx-6 -my-5 grid h-[calc(100vh-3.5rem)] min-h-0 lg:grid-cols-[264px_1fr]">
      <aside className="hidden min-h-0 border-r border-line bg-white p-3 lg:block">{history}</aside>

      <section className="flex min-h-0 min-w-0 flex-col" aria-label="Ask SapulMRF">
        <div className="flex items-center gap-3 border-b border-line bg-white px-5 py-2.5">
          <h1 className="text-lg font-extrabold whitespace-nowrap">Ask SapulMRF</h1>
          <span className="hidden min-w-0 truncate text-sm text-muted sm:block">{chat.data?.title}</span>
          <button type="button" className={`${btn.base} ${btn.secondary} ${btn.small} ml-auto lg:hidden`} onClick={() => setDrawer(true)}>History</button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5" aria-live="polite">
          {empty ? (
            <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 pt-[8vh] text-center">
              <span className="grid size-12 place-items-center rounded-2xl bg-leaf-700 text-white"><Icon name="ask" className="size-6" /></span>
              <h2 className="text-2xl font-extrabold text-ink">What do you want to know about the MRF?</h2>
              <p className="max-w-md text-sm text-ink-2">
                Ask about intake, segregation, storage, compost, sales, forecasts or the camera, in English or Tagalog.
                Add a purok, a material or dates to narrow it down. Answers come straight from SapulMRF's records.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {suggestions.map((s) => (
                  <button key={s} type="button" onClick={() => send(s)}
                    className={`${focus} rounded-full border border-edge bg-white px-3.5 py-1.5 text-sm text-ink hover:border-leaf-600 hover:bg-leaf-100/50`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {chat.isLoading && <p className="text-sm text-muted">Loading the chat…</p>}
              {chat.isError && <p role="alert" className="text-sm text-crit">This chat couldn't be opened. It may have been deleted.</p>}
              {messages.map((m, i) =>
                m.role === 'user' ? (
                  <p key={m.id} className="ml-auto max-w-[80%] rounded-2xl rounded-tr-sm bg-leaf-700 px-4 py-2 text-sm text-white">{m.text}</p>
                ) : (
                  m.answer && (
                    <AnswerView key={m.id} message={m} question={messages[i - 1]?.text ?? ''} busy={ask.isPending}
                      onAsk={send} onFeedback={(helpful, corrected) => feedback.mutate({ id: m.id, helpful, corrected_intent: corrected })} />
                  )
                ),
              )}
              {pending && (
                <>
                  <p className="ml-auto max-w-[80%] rounded-2xl rounded-tr-sm bg-leaf-700 px-4 py-2 text-sm text-white">{pending}</p>
                  <p className="flex w-16 justify-center gap-1 rounded-2xl rounded-tl-sm bg-white px-3 py-3 ring-1 ring-line" aria-label="Answering">
                    {[0, 150, 300].map((d) => <span key={d} className="size-1.5 rounded-full bg-leaf-600 motion-safe:animate-pulse" style={{ animationDelay: `${d}ms` }} />)}
                  </p>
                </>
              )}
              <div ref={end} />
            </div>
          )}
        </div>

        <form className="border-t border-line bg-white px-5 py-3" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          {ask.isError && <p role="alert" className="mx-auto mb-2 max-w-3xl text-sm text-crit">{ask.error.message} Your question is still in the box.</p>}
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-edge bg-white p-1.5 focus-within:border-leaf-700">
            <textarea
              ref={box}
              rows={1}
              value={text}
              maxLength={500}
              aria-label="Your question"
              placeholder="Ask about intake, storage, compost, sales…"
              className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2.5 py-1.5 text-sm outline-none"
              onChange={(e) => { setText(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${e.target.scrollHeight}px`; }}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text); } }}
            />
            <button className={`${btn.base} ${btn.primary} rounded-xl`} disabled={!text.trim() || ask.isPending}>Ask</button>
          </div>
          <p className="mx-auto mt-1 max-w-3xl px-1 text-[11px] text-muted">Enter to ask · Shift+Enter for a new line · No AI model: answers are SapulMRF's own numbers.</p>
        </form>
      </section>

      {drawer && (
        <Drawer title="Past chats" onClose={() => setDrawer(false)} footer={null}>
          {history}
        </Drawer>
      )}
    </div>
  );
}
