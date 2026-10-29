import type { AnalyzeResponse } from './models/types.js';
import { parseLines, type StreamEvent } from './stream.js';

export const DEFAULT_BACKEND = 'http://127.0.0.1:8000';
const STORAGE_KEY = 'backendUrl';

export type BackendErrorKind = 'offline' | 'timeout' | 'http' | 'bad_response' | 'cancelled';

export class BackendError extends Error {
  constructor(
    public readonly kind: BackendErrorKind,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'BackendError';
  }
}

/** Only loopback addresses are allowed: they are the only hosts the manifest grants. */
export function normalizeBackendUrl(raw: string): string | null {
  try {
    const u = new URL(raw.trim());
    const loopback = u.hostname === '127.0.0.1' || u.hostname === 'localhost';
    if (u.protocol !== 'http:' || !loopback) return null;
    return u.origin;
  } catch {
    return null;
  }
}

export async function getBackendUrl(): Promise<string> {
  try {
    const stored = await chrome.storage.local.get(STORAGE_KEY);
    const value = stored[STORAGE_KEY];
    if (typeof value === 'string') return normalizeBackendUrl(value) ?? DEFAULT_BACKEND;
  } catch {
    /* storage unavailable: fall back to default */
  }
  return DEFAULT_BACKEND;
}

export async function setBackendUrl(url: string): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: url });
}

function withTimeout(ms: number, outer?: AbortSignal): { signal: AbortSignal; done: () => void; timedOut: () => boolean } {
  const ctrl = new AbortController();
  let fired = false;
  const timer = setTimeout(() => {
    fired = true;
    ctrl.abort();
  }, ms);
  const onOuter = () => ctrl.abort();
  outer?.addEventListener('abort', onOuter);
  return {
    signal: ctrl.signal,
    timedOut: () => fired,
    done: () => {
      clearTimeout(timer);
      outer?.removeEventListener('abort', onOuter);
    },
  };
}

export interface BackendInfo {
  verdict_mode: string;
  retrievers: string[];
}

export interface Health {
  reachable: boolean;
  /** Models loaded and configuration valid: analysis requests will be served. */
  ready: boolean;
  /** Setup problem reported by the backend, e.g. a missing API key. */
  error: string | null;
  /** Non-secret configuration, when the backend reports it. */
  info: BackendInfo | null;
}

export async function checkHealth(base: string, timeoutMs = 2500): Promise<Health> {
  const t = withTimeout(timeoutMs);
  try {
    const res = await fetch(`${base}/health`, { signal: t.signal });
    if (!res.ok) return { reachable: false, ready: false, error: null, info: null };
    const body = (await res.json().catch(() => ({}))) as {
      pipeline_ready?: boolean;
      pipeline_error?: string | null;
      info?: { verdict_mode?: unknown; retrievers?: unknown } | null;
    };
    const rawInfo = body.info;
    const info =
      rawInfo && typeof rawInfo.verdict_mode === 'string' && Array.isArray(rawInfo.retrievers)
        ? { verdict_mode: rawInfo.verdict_mode, retrievers: rawInfo.retrievers.map(String) }
        : null;
    return {
      reachable: true,
      // Older backends have no readiness field: treat a healthy reply as ready.
      ready: body.pipeline_ready ?? true,
      error: typeof body.pipeline_error === 'string' ? body.pipeline_error : null,
      info,
    };
  } catch {
    return { reachable: false, ready: false, error: null, info: null };
  } finally {
    t.done();
  }
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    /* non-JSON error body */
  }
  return '';
}

/**
 * Streams the analysis: `onEvent` is called as each NDJSON line arrives. Resolves once the server
 * sent its terminal line. A connection that closes before that is an error, never a partial success.
 * Falls back to the one-shot endpoint when the backend predates streaming.
 */
export async function analyzeStream(
  base: string,
  text: string,
  onEvent: (event: StreamEvent) => void,
  cancel?: AbortSignal,
  timeoutMs = 240_000,
): Promise<void> {
  const t = withTimeout(timeoutMs, cancel);
  try {
    let res: Response;
    try {
      res = await fetch(`${base}/api/v1/analyze/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_text: text }),
        signal: t.signal,
      });
    } catch {
      if (cancel?.aborted) throw new BackendError('cancelled', 'Cancelled.');
      if (t.timedOut()) throw new BackendError('timeout', 'The backend took too long to answer.');
      throw new BackendError('offline', 'Could not reach the backend.');
    }

    if (res.status === 404 || res.status === 405) {
      t.done();
      const data = await analyze(base, text, cancel);
      onEvent({
        type: 'claims',
        claims: data.results.map((r) => r.claim),
        truncated: data.truncated === true,
      });
      data.results.forEach((result, index) => onEvent({ type: 'claim', index, result }));
      onEvent({ type: 'done' });
      return;
    }
    if (!res.ok) {
      throw new BackendError('http', (await readDetail(res)) || `Backend returned status ${res.status}.`, res.status);
    }
    if (!res.body) throw new BackendError('bad_response', 'The backend sent no response body.');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let terminal = false;
    const deliver = (events: StreamEvent[]) => {
      for (const e of events) {
        if (e.type === 'done' || e.type === 'error') terminal = true;
        onEvent(e);
      }
    };

    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseLines(buffer);
        buffer = parsed.rest;
        deliver(parsed.events);
      }
      buffer += decoder.decode();
      deliver(parseLines(buffer + '\n').events);
    } catch (err) {
      if (err instanceof BackendError) throw err;
      if (cancel?.aborted) throw new BackendError('cancelled', 'Cancelled.');
      if (t.timedOut()) throw new BackendError('timeout', 'The backend took too long to answer.');
      throw new BackendError('offline', 'The connection to the backend was lost.');
    }

    if (!terminal) {
      throw new BackendError('bad_response', 'The connection closed before the analysis finished.');
    }
  } finally {
    t.done();
  }
}

export async function analyze(
  base: string,
  text: string,
  cancel?: AbortSignal,
  timeoutMs = 120_000,
): Promise<AnalyzeResponse> {
  const t = withTimeout(timeoutMs, cancel);
  let res: Response;
  try {
    res = await fetch(`${base}/api/v1/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_text: text }),
      signal: t.signal,
    });
  } catch (err) {
    if (cancel?.aborted) throw new BackendError('cancelled', 'Cancelled.');
    if (t.timedOut()) throw new BackendError('timeout', 'The backend took too long to answer.');
    throw new BackendError('offline', 'Could not reach the backend.');
  } finally {
    t.done();
  }

  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new BackendError('http', detail || `Backend returned status ${res.status}.`, res.status);
  }

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new BackendError('bad_response', 'The backend sent a response that is not valid JSON.');
  }
  const body = data as Partial<AnalyzeResponse> | null;
  if (!body || !Array.isArray(body.results)) {
    throw new BackendError('bad_response', 'The backend response is missing a results list.');
  }
  return { results: body.results, truncated: body.truncated === true };
}
