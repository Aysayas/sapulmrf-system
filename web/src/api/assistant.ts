import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { ReportKind } from './reports';

export type Card = { label: string; value: string; delta: string | null };
export type Chart = { kind: 'bar' | 'line'; x: string[]; series: { name: string; values: number[] }[] };
export type ExportRef = { kind: ReportKind; from_day: string; to_day: string; area: number | null };
export type Answer = {
  intent: string;
  title: string;
  summary: string;
  cards: Card[];
  table: { columns: string[]; rows: (string | number | null)[][] } | null;
  chart: Chart | null;
  export: ExportRef | null;
  note: string | null;
  suggestions: string[];
  show: ('chart' | 'table' | 'export')[]; // what the question asked to see; the rest is offered
  steps: string[]; // how-to answers: what to click, in order
  links: { label: string; to: string }[]; // pages on this website the answer points to
};
export type Message = { id: number; role: 'user' | 'assistant'; text: string; answer: Answer | null; helpful: boolean | null; created_at: string };
export type Conversation = { id: number; title: string; updated_at: string };
export type ConversationDetail = Conversation & { messages: Message[] };
export type AskOut = { conversation_id: number; user: Message; assistant: Message };

/** The topics the chat knows, for "Did you mean" and 👎 corrections. */
export const TOPICS: [string, string][] = [
  ['today', 'Today'], ['intake', 'Intake'], ['segregation', 'Segregation'], ['storage', 'Storage'], ['compost', 'Compost'],
  ['outgoing', 'Outgoing'], ['income', 'Income'], ['forecast', 'Forecast'], ['unusual', 'Unusual deliveries'],
  ['attention', 'Needs attention'], ['camera', 'Camera accuracy'],
];

export function useConversations() {
  return useQuery({ queryKey: ['assistant', 'conversations'], queryFn: () => api<Conversation[]>('/assistant/conversations') });
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: ['assistant', 'conversation', id],
    queryFn: () => api<ConversationDetail>(`/assistant/conversations/${id}`),
    enabled: id !== null,
  });
}

export function useSuggestions() {
  return useQuery({ queryKey: ['assistant', 'suggestions'], queryFn: () => api<string[]>('/assistant/suggestions'), staleTime: Infinity });
}

export function useAsk() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { text: string; conversation_id?: number | null; intent?: string }) =>
      api<AskOut>('/assistant/ask', { method: 'POST', body }),
    onSuccess: (out) => {
      qc.invalidateQueries({ queryKey: ['assistant', 'conversations'] });
      qc.invalidateQueries({ queryKey: ['assistant', 'conversation', out.conversation_id] });
    },
  });
}

export function useRename() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) => api<Conversation>(`/assistant/conversations/${id}`, { method: 'PATCH', body: { title } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant'] }),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/assistant/conversations/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant', 'conversations'] }),
  });
}

export function useFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, helpful, corrected_intent }: { id: number; helpful: boolean; corrected_intent?: string }) =>
      api<void>(`/assistant/messages/${id}/feedback`, { method: 'POST', body: { helpful, corrected_intent } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant', 'conversation'] }),
  });
}
