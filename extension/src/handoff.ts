/**
 * Hand-off from the service worker (context menu, keyboard shortcut) to the side panel.
 *
 * The worker opens the panel and stores the selected text under PENDING_KEY in storage.session.
 * The panel consumes it on load, or from a storage change if it was already open. Pure parts
 * here; the chrome.* calls are injected so the flow can be unit-tested.
 */

export const PENDING_KEY = 'pendingCheck';
export const MENU_ID = 'ss-check-selection';
export const COMMAND_ID = 'check-selection';
export const MAX_AGE_MS = 2 * 60 * 1000;

export interface Pending {
  text: string;
  at: number;
}

export function makePending(text: string | undefined, now: number): Pending | null {
  const trimmed = (text ?? '').trim();
  return trimmed ? { text: trimmed, at: now } : null;
}

export function isFresh(value: unknown, now: number): value is Pending {
  const v = value as Partial<Pending> | null;
  return (
    !!v &&
    typeof v.text === 'string' &&
    v.text.trim().length > 0 &&
    typeof v.at === 'number' &&
    now - v.at >= 0 &&
    now - v.at <= MAX_AGE_MS
  );
}

export interface WorkerDeps {
  openPanel(target: { tabId?: number; windowId?: number }): Promise<void>;
  store(key: string, value: Pending): Promise<void>;
  readSelection(tabId: number): Promise<string>;
  now(): number;
}

/**
 * Context-menu click: the selection text arrives with the event.
 * The panel is opened first, synchronously with the user gesture; storing happens after.
 */
export async function handleMenuClick(
  selectionText: string | undefined,
  tab: { id?: number; windowId?: number } | undefined,
  deps: WorkerDeps,
): Promise<'queued' | 'empty' | 'no_tab'> {
  if (!tab) return 'no_tab';
  const opening = deps.openPanel({ tabId: tab.id, windowId: tab.windowId });
  const pending = makePending(selectionText, deps.now());
  await opening.catch(() => undefined);
  if (!pending) return 'empty';
  await deps.store(PENDING_KEY, pending);
  return 'queued';
}

/** Keyboard shortcut: the selection has to be read from the page first. */
export async function handleShortcut(
  tab: { id?: number; windowId?: number } | undefined,
  deps: WorkerDeps,
): Promise<'queued' | 'empty' | 'no_tab' | 'unreadable'> {
  if (!tab?.id) return 'no_tab';
  const opening = deps.openPanel({ tabId: tab.id, windowId: tab.windowId });
  let text = '';
  try {
    text = await deps.readSelection(tab.id);
  } catch {
    await opening.catch(() => undefined);
    return 'unreadable';
  }
  await opening.catch(() => undefined);
  const pending = makePending(text, deps.now());
  if (!pending) return 'empty';
  await deps.store(PENDING_KEY, pending);
  return 'queued';
}
