import { applyHighlights, clearHighlights, readPageSelection, scrollToHighlight, type HighlightItem } from './inject.js';
import type { Verdict } from './present.js';

/** Panel-side bridge to the active tab. Everything here fails soft with a typed reason. */

export type PageAccessReason = 'no_tab' | 'blocked' | 'unsupported';

export class PageAccessError extends Error {
  constructor(
    public readonly reason: PageAccessReason,
    message: string,
  ) {
    super(message);
    this.name = 'PageAccessError';
  }
}

export function kindFor(verdict: Verdict): HighlightItem['kind'] {
  if (verdict === 'supported') return 'supported';
  if (verdict === 'refuted') return 'refuted';
  if (verdict === 'mixed') return 'mixed';
  return 'neutral';
}

async function activeTabId(): Promise<number> {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.id) throw new PageAccessError('no_tab', 'There is no active tab.');
  return tab.id;
}

async function run<A extends unknown[], R>(func: (...args: A) => R, args: A): Promise<R> {
  const tabId = await activeTabId();
  try {
    const [injected] = await chrome.scripting.executeScript({ target: { tabId }, func, args });
    return injected?.result as R;
  } catch {
    // chrome:// pages, the Web Store, and tabs we have no permission for all land here.
    throw new PageAccessError('blocked', 'Chrome does not let extensions read this page.');
  }
}

export async function readSelection(): Promise<string> {
  const text = await run(readPageSelection, []);
  return typeof text === 'string' ? text.trim() : '';
}

export interface ClaimToHighlight {
  text: string;
  context?: string;
  verdict: Verdict;
}

/** Returns, per claim, whether it was found on the page. */
export async function highlight(claims: ClaimToHighlight[]): Promise<boolean[]> {
  const items: HighlightItem[] = claims.map((c) => ({
    needles: [c.text, c.context ?? ''].filter((s) => s.trim().length > 0),
    kind: kindFor(c.verdict),
  }));
  const outcome = await run(applyHighlights, [items]);
  return outcome?.found ?? items.map(() => false);
}

export async function clear(): Promise<void> {
  await run(clearHighlights, []);
}

export async function scrollTo(index: number): Promise<boolean> {
  return (await run(scrollToHighlight, [index])) === true;
}
