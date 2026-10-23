export class ApiError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}
/** Every backend call goes through here: same-origin /api (Vite proxy), session cookie included, JSON in and out. */
export async function api(path, options = {}) {
    const res = await fetch(`/api${path}`, {
        method: options.method ?? 'GET',
        credentials: 'include',
        headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
    if (res.status === 204)
        return undefined;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Something went wrong. Check the form and try again.';
        throw new ApiError(res.status, detail);
    }
    return data;
}
/** Fetches a file from the API and hands it to the browser as a download (the session cookie goes along). */
export async function download(path) {
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
