export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Every backend call goes through here: same-origin /api (Vite proxy), session cookie included, JSON in and out. */
export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: options.method ?? 'GET',
    credentials: 'include',
    headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Something went wrong. Check the form and try again.';
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

/** Fetches a file from the API and hands it to the browser as a download (the session cookie goes along). */
export async function download(path: string): Promise<void> {
  const res = await fetch(`/api${path}`, { credentials: 'include' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof data.detail === 'string' ? data.detail : 'The download failed.');
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'download';
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

const KEY_LIFETIME_MS = 10 * 60_000;

/**
 * Gives one submission a client_key, kept in this tab until it succeeds. If a response is lost and the operator sends
 * the same values again, even after closing the form or reloading, the server returns the first record.
 */
export async function once<In extends object, Out>(path: string, body: In, send: (keyed: In & { client_key: string }) => Promise<Out>) {
  const slot = `once:${path}`;
  const text = JSON.stringify(body);
  let saved: { body: string; key: string; at: number } | null = null;
  try {
    saved = JSON.parse(sessionStorage.getItem(slot) ?? 'null');
  } catch {
    // shortcut: without storage, only a double tap is protected.
  }
  if (saved?.body !== text || Date.now() - saved.at > KEY_LIFETIME_MS) {
    // Not crypto.randomUUID: phones reach a LAN server over plain http until HTTPS is set up.
    const key = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
    saved = { body: text, key, at: Date.now() };
    try {
      sessionStorage.setItem(slot, JSON.stringify(saved));
    } catch {
      // as above
    }
  }
  const out = await send({ ...body, client_key: saved.key });
  try {
    sessionStorage.removeItem(slot);
  } catch {
    // as above
  }
  return out;
}
