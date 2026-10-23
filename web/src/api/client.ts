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
