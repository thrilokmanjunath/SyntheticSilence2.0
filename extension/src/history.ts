import type { ClaimResult } from './models/types.js';

/**
 * Local history of finished checks (chrome.storage.local). The list logic is pure; the storage
 * wrappers at the bottom are thin so they can be exercised with a fake `chrome.storage`.
 */

export const HISTORY_KEY = 'history';
export const MAX_ENTRIES = 30;
export const MAX_SOURCE_CHARS = 400;
export const MAX_QUOTA_BYTES = 3_000_000; // storage.local allows far more; stay well clear of it

export interface HistoryEntry {
  id: string;
  at: number;
  /** First part of the checked text, for the list. */
  preview: string;
  results: ClaimResult[];
}

/** Drops fields that are large and not needed to re-open a result. */
export function compact(results: ClaimResult[]): ClaimResult[] {
  return results.map((r) => ({
    ...r,
    claim: { ...r.claim, context: '' },
    evidence: (r.evidence ?? []).map((e) => ({
      ...e,
      text: e.text.length > MAX_SOURCE_CHARS ? e.text.slice(0, MAX_SOURCE_CHARS) : e.text,
    })),
  }));
}

export function makeEntry(text: string, results: ClaimResult[], now: number, id?: string): HistoryEntry {
  return {
    id: id ?? `${now.toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    at: now,
    preview: text.replace(/\s+/g, ' ').trim().slice(0, 160),
    results: compact(results),
  };
}

/** Newest first. A repeat of the same text replaces the older entry rather than stacking up. */
export function addEntry(list: HistoryEntry[], entry: HistoryEntry): HistoryEntry[] {
  const without = list.filter((e) => e.preview !== entry.preview);
  const next = [entry, ...without].slice(0, MAX_ENTRIES);

  // Stay under the byte budget by dropping the oldest entries first.
  while (next.length > 1 && JSON.stringify(next).length > MAX_QUOTA_BYTES) next.pop();
  return next;
}

export function removeEntry(list: HistoryEntry[], id: string): HistoryEntry[] {
  return list.filter((e) => e.id !== id);
}

export function relativeTime(at: number, now: number): string {
  const s = Math.max(0, Math.round((now - at) / 1000));
  if (s < 60) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const hrs = Math.round(m / 60);
  if (hrs < 24) return `${hrs} h ago`;
  const d = Math.round(hrs / 24);
  return d === 1 ? 'yesterday' : `${d} days ago`;
}

function isEntry(value: unknown): value is HistoryEntry {
  const v = value as Partial<HistoryEntry> | null;
  return !!v && typeof v.id === 'string' && typeof v.at === 'number' && typeof v.preview === 'string' && Array.isArray(v.results);
}

export async function loadHistory(): Promise<HistoryEntry[]> {
  try {
    const stored = await chrome.storage.local.get(HISTORY_KEY);
    const raw = stored[HISTORY_KEY];
    return Array.isArray(raw) ? raw.filter(isEntry) : [];
  } catch {
    return [];
  }
}

export async function saveHistory(list: HistoryEntry[]): Promise<void> {
  try {
    await chrome.storage.local.set({ [HISTORY_KEY]: list });
  } catch {
    /* quota or storage unavailable: history is a convenience, never an error */
  }
}
