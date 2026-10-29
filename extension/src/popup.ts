import {
  analyzeStream, BackendError, checkHealth, DEFAULT_BACKEND, getBackendUrl, normalizeBackendUrl, setBackendUrl,
} from './api.js';
import { badgeFor, CLEARED, FAILED, setBadge, WORKING } from './badge.js';
import { byId, h } from './dom.js';
import { toJson, toMarkdown } from './export.js';
import { isFresh, PENDING_KEY } from './handoff.js';
import {
  addEntry, loadHistory, makeEntry, relativeTime, removeEntry, saveHistory, type HistoryEntry,
} from './history.js';
import type { ClaimResult } from './models/types.js';
import * as page from './page.js';
import { summarize, toClaimView, type ClaimView } from './present.js';
import {
  initialState, progress, reduce, retrySlot, type Slot, type StreamEvent, type StreamState,
} from './stream.js';
import { claimItem, silentMeter } from './views.js';

const MAX_CHARS = 4000;
const DRAFT_KEY = 'draft';
const RESEARCH_KEY = 'researchMode';
const THEME_KEY = 'theme';
// Run from the repository root; --app-dir keeps it a single command in any shell.
const START_COMMAND = 'python -m uvicorn app.main:app --app-dir backend --port 8000';
const EXAMPLE_TEXT =
  'The Great Wall of China is visible from space with the naked eye. ' +
  'Honey never spoils when stored in a sealed container.';

const els = {
  input: byId<HTMLTextAreaElement>('inputText'),
  count: byId<HTMLElement>('count'),
  analyze: byId<HTMLButtonElement>('analyzeBtn'),
  grab: byId<HTMLButtonElement>('grabBtn'),
  panel: byId<HTMLButtonElement>('panelBtn'),
  historyBtn: byId<HTMLButtonElement>('historyBtn'),
  output: byId<HTMLElement>('output'),
  status: byId<HTMLElement>('status'),
  statusText: byId<HTMLElement>('statusText'),
  backendUrl: byId<HTMLInputElement>('backendUrl'),
  saveBackend: byId<HTMLButtonElement>('saveBackend'),
  backendMsg: byId<HTMLElement>('backendMsg'),
  research: byId<HTMLInputElement>('researchMode'),
  theme: byId<HTMLSelectElement>('theme'),
  backendInfo: byId<HTMLElement>('backendInfo'),
};

let backend = DEFAULT_BACKEND;
let inFlight: AbortController | null = null;
let research = false; // shows the experimental density/entropy signals
let lastText = '';
let tabId: number | undefined;

/* ---------- status + environment ---------- */

function setStatus(state: 'checking' | 'ready' | 'offline', text: string): void {
  els.status.dataset.state = state;
  els.statusText.textContent = text;
}

let warmupTimer: number | undefined;

async function refreshHealth(): Promise<boolean> {
  window.clearTimeout(warmupTimer);
  setStatus('checking', 'Checking backend');
  const health = await checkHealth(backend);
  const host = new URL(backend).host;

  // Short text keeps the header on one line in a 420px popup; the address is in the tooltip.
  els.status.title = host;
  if (!health.reachable) {
    setStatus('offline', 'Backend not running');
    els.backendInfo.textContent = '';
  } else if (health.error) {
    setStatus('offline', 'Backend needs setup');
    els.status.title = health.error;
  } else if (!health.ready) {
    // Models are still loading: poll until ready so the status updates by itself.
    setStatus('checking', 'Backend warming up');
    warmupTimer = window.setTimeout(() => void refreshHealth(), 3000);
  } else {
    setStatus('ready', 'Backend ready');
    if (health.info) {
      const mode = health.info.verdict_mode === 'stance' ? 'per-source stance' : 'pooled score';
      els.backendInfo.textContent = `Backend: ${mode}; sources: ${health.info.retrievers.join(', ')}.`;
    }
  }
  return health.reachable;
}

async function detectSidePanel(): Promise<void> {
  try {
    const contexts = await chrome.runtime.getContexts({ contextTypes: ['SIDE_PANEL' as chrome.runtime.ContextType] });
    if (contexts.length > 0) {
      document.documentElement.classList.replace('is-popup', 'is-panel');
      els.panel.hidden = true;
    }
  } catch {
    /* older Chrome: stay in popup layout */
  }
}

function applyTheme(theme: string): void {
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
  else document.documentElement.removeAttribute('data-theme');
}

/* ---------- input ---------- */

function updateCount(): void {
  const n = els.input.value.length;
  els.count.textContent = `${n.toLocaleString()} / ${MAX_CHARS.toLocaleString()}`;
  els.count.dataset.near = String(n > MAX_CHARS * 0.9);
  els.analyze.disabled = els.input.value.trim().length === 0 || inFlight !== null;
}

let draftTimer: number | undefined;
function saveDraft(): void {
  window.clearTimeout(draftTimer);
  draftTimer = window.setTimeout(() => {
    chrome.storage.local.set({ [DRAFT_KEY]: els.input.value }).catch(() => undefined);
  }, 300);
}

function setInput(text: string): void {
  els.input.value = text.slice(0, MAX_CHARS);
  updateCount();
  saveDraft();
}

async function useSelection(quiet: boolean): Promise<void> {
  try {
    const selected = await page.readSelection();
    if (selected) {
      setInput(selected);
      els.input.focus();
    } else if (!quiet) {
      renderNotice('Nothing selected', 'Highlight some text on the page, then choose Use page selection again.');
    }
  } catch {
    if (!quiet) {
      renderNotice(
        'Can’t read this page',
        'Chrome blocks extensions on pages like the Web Store and chrome:// tabs. Paste the text here instead.',
      );
    }
  }
}

/* ---------- simple states ---------- */

function clearOutput(): void {
  els.output.replaceChildren();
  els.output.removeAttribute('aria-busy');
}

function renderIdle(): void {
  clearOutput();
  const example = h('button', { type: 'button', class: 'link' }, 'Try an example');
  example.addEventListener('click', () => {
    setInput(EXAMPLE_TEXT);
    els.input.focus();
  });
  els.output.append(
    h(
      'div',
      { class: 'empty' },
      h('h2', {}, 'Check what the sources say'),
      h(
        'p',
        {},
        'Paste text or select it on a page. Each factual claim is matched against sources and shown with how much they back it up or push against it.',
      ),
      h('p', {}, 'You can also select text, right-click, and choose Check evidence, or press Alt+Shift+S.'),
      example,
    ),
  );
}

function renderNotice(title: string, body: string, extra?: Node): void {
  clearOutput();
  const box = h('div', { class: 'notice', role: 'alert' }, h('h2', {}, title), h('p', {}, body));
  if (extra) box.append(extra);
  els.output.append(box);
}

function renderLoading(): void {
  clearOutput();
  els.output.setAttribute('aria-busy', 'true');
  const cancel = h('button', { type: 'button', class: 'link' }, 'Cancel');
  cancel.addEventListener('click', () => inFlight?.abort());
  els.output.append(
    h(
      'div',
      { class: 'loading' },
      h('h2', {}, 'Checking claims'),
      h('p', {}, 'Extracting claims and searching sources. The first check can take a minute while models load.'),
      h('div', { class: 'skeleton', 'aria-hidden': 'true' }, h('span'), h('span'), h('span')),
      cancel,
    ),
  );
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = h('textarea', { 'aria-hidden': 'true' });
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

function copyButton(label: string, produce: () => string, cls = 'btn ghost'): HTMLButtonElement {
  const btn = h('button', { type: 'button', class: cls }, label);
  btn.addEventListener('click', async () => {
    const ok = await copyText(produce());
    btn.textContent = ok ? 'Copied' : 'Copy failed';
    window.setTimeout(() => {
      btn.textContent = label;
    }, 1600);
  });
  return btn;
}

function renderOffline(): void {
  const code = h('code', {}, START_COMMAND);
  const retry = h('button', { type: 'button', class: 'btn ghost' }, 'Check again');
  retry.addEventListener('click', async () => {
    if (await refreshHealth()) renderIdle();
  });
  renderNotice(
    'Can’t reach the backend',
    'Run this from the project root, then check again.',
    h('div', { class: 'cmd' }, code, h('div', { class: 'row' }, copyButton('Copy command', () => START_COMMAND), retry)),
  );
}

/* ---------- streaming results ---------- */

let state: StreamState = initialState();
let headEl: HTMLElement | null = null;
let slotEls: HTMLElement[] = [];
// Which done claims were found on the page after "Highlight on page"; null when not highlighted.
let onPage: Map<number, boolean> | null = null;
let highlightNote: HTMLElement | null = null;
let actionsEl: HTMLElement | null = null;

function doneResults(): ClaimResult[] {
  return state.slots.flatMap((s) => (s.status === 'done' ? [s.result] : []));
}

function slotItem(slot: Slot, index: number): HTMLElement {
  if (slot.status === 'done') {
    return claimItem(toClaimView(slot.result, { research }), {
      onPage: onPage ? (onPage.get(index) ?? false) : null,
      onShow: () => void showOnPage(index),
    });
  }
  if (slot.status === 'pending') {
    return h(
      'li',
      { class: 'claim is-pending', 'aria-busy': 'true' },
      h('blockquote', {}, slot.text),
      h('div', { class: 'readout' }, silentMeter(), h('p', { class: 'verdict' }, 'Checking sources')),
    );
  }
  const retry = h('button', { type: 'button', class: 'link' }, 'Try this claim again');
  retry.addEventListener('click', () => void retryClaim(index));
  return h(
    'li',
    { class: 'claim is-error' },
    h('blockquote', {}, slot.text),
    h('div', { class: 'readout' }, silentMeter(), h('p', { class: 'verdict' }, 'Couldn’t check this claim')),
    h('p', { class: 'why' }, slot.error.message),
    retry,
  );
}

function paintHead(): void {
  if (!headEl) return;
  headEl.replaceChildren();
  const { finished, total } = progress(state);

  if (state.slots.some((s) => s.status === 'pending')) {
    headEl.append(
      h('h2', {}, `Checking ${total} ${total === 1 ? 'claim' : 'claims'}`),
      h('p', {}, `${finished} of ${total} finished`),
    );
    return;
  }

  const views: ClaimView[] = doneResults().map((r) => toClaimView(r, { research }));
  const failed = state.slots.filter((s) => s.status === 'error').length;
  const summary = summarize(views);
  const detail = [summary.detail, failed ? `${failed} couldn’t be checked` : ''].filter(Boolean).join(', ');

  headEl.append(h('h2', {}, total === 1 ? '1 claim found' : `${total} claims found`));
  if (detail) headEl.append(h('p', {}, detail));
  if (state.truncated) {
    headEl.append(h('p', {}, `Showing the first ${total}. Check the rest in a separate passage.`));
  }
}

function paintActions(): void {
  if (!actionsEl) return;
  actionsEl.replaceChildren();
  const results = doneResults();
  const finished = !state.slots.some((s) => s.status === 'pending');
  if (!finished || results.length === 0) return;

  const ctx = () => ({ checkedAt: new Date(), sourceText: lastText });
  const highlighted = onPage !== null;
  const toggle = h('button', { type: 'button', class: 'btn ghost' }, highlighted ? 'Clear highlights' : 'Highlight on page');
  toggle.addEventListener('click', () => void (highlighted ? clearOnPage() : highlightOnPage()));

  actionsEl.append(
    toggle,
    copyButton('Copy as Markdown', () => toMarkdown(doneResults(), ctx())),
    copyButton('Copy JSON', () => toJson(doneResults(), ctx())),
  );
}

function setHighlightNote(text: string): void {
  if (highlightNote) highlightNote.textContent = text;
}

function buildList(): void {
  clearOutput();
  onPage = null;
  headEl = h('div', { class: 'summary' });
  actionsEl = h('div', { class: 'row actions' });
  highlightNote = h('p', { class: 'hint', role: 'status' });
  els.output.append(
    headEl,
    actionsEl,
    highlightNote,
    h(
      'p',
      { class: 'caveat' },
      'Automated check. A language model reads a few retrieved sources, so a verdict can be wrong. Open the sources before relying on one.',
    ),
  );
  slotEls = state.slots.map((s, i) => slotItem(s, i));
  els.output.append(h('ul', { class: 'claims' }, ...slotEls));
  paintHead();
  paintActions();
}

function repaintSlot(index: number): void {
  const slot = state.slots[index];
  const current = slotEls[index];
  if (!slot || !current) return;
  const next = slotItem(slot, index);
  current.replaceWith(next);
  slotEls[index] = next;
}

/** Re-renders every claim, e.g. after the research-mode toggle. */
function renderAll(): void {
  if (state.slots.length === 0) return;
  state.slots.forEach((_, i) => repaintSlot(i));
  paintHead();
  paintActions();
}

function finishBadge(): void {
  const views = doneResults().map((r) => toClaimView(r, { research }));
  const failed = state.slots.some((s) => s.status === 'error');
  void setBadge(views.length === 0 && failed ? FAILED : badgeFor(views.map((v) => v.verdict)), tabId);
}

async function remember(): Promise<void> {
  const results = doneResults();
  if (results.length === 0) return;
  const list = await loadHistory();
  await saveHistory(addEntry(list, makeEntry(lastText, results, Date.now())));
}

function onStreamEvent(event: StreamEvent): void {
  state = reduce(state, event);
  switch (event.type) {
    case 'claims':
      if (state.slots.length > 0) buildList();
      break;
    case 'claim':
    case 'claim_error':
      repaintSlot(event.index);
      paintHead();
      break;
    case 'done':
      if (state.slots.length === 0) {
        renderNotice(
          'No factual claims found',
          'The text had nothing the system could check, such as opinions or questions. Try a more specific statement.',
        );
        void setBadge(CLEARED, tabId);
      } else {
        paintHead();
        paintActions();
        finishBadge();
        void remember();
      }
      break;
    case 'error':
      renderNotice('The backend hit a problem', event.error.message);
      void setBadge(FAILED, tabId);
      break;
  }
}

/** Marks every still-pending claim as failed so a lost connection never leaves a spinner behind. */
function failPending(kind: string, message: string): void {
  state.slots.forEach((slot, index) => {
    if (slot.status !== 'pending') return;
    state = reduce(state, { type: 'claim_error', index, error: { kind, message } });
    repaintSlot(index);
  });
  paintHead();
  paintActions();
}

async function retryClaim(index: number): Promise<void> {
  const slot = state.slots[index];
  if (!slot || inFlight) return;

  inFlight = new AbortController();
  updateCount();
  state = retrySlot(state, index);
  repaintSlot(index);
  paintHead();
  paintActions();

  let settled = false;
  try {
    await analyzeStream(
      backend,
      slot.text,
      (event) => {
        if (settled) return;
        if (event.type === 'claim') {
          settled = true;
          state = reduce(state, { ...event, index });
        } else if (event.type === 'claim_error' || event.type === 'error') {
          settled = true;
          state = reduce(state, { type: 'claim_error', index, error: event.error });
        }
      },
      inFlight.signal,
    );
  } catch (err) {
    const e = err instanceof BackendError ? err : new BackendError('http', String(err));
    state = reduce(state, { type: 'claim_error', index, error: { kind: e.kind, message: e.message } });
    settled = true;
  } finally {
    if (!settled) {
      state = reduce(state, {
        type: 'claim_error', index,
        error: { kind: 'no_claim', message: 'No checkable claim was found in this text.' },
      });
    }
    inFlight = null;
    repaintSlot(index);
    paintHead();
    paintActions();
    updateCount();
    finishBadge();
    void remember();
  }
}

/* ---------- on-page highlighting ---------- */

async function highlightOnPage(): Promise<void> {
  const entries = state.slots.flatMap((s, index) => {
    if (s.status !== 'done') return [];
    const view = toClaimView(s.result, { research });
    return [{ index, text: view.text, context: s.result.claim.context, verdict: view.verdict }];
  });
  if (entries.length === 0) return;

  try {
    const found = await page.highlight(entries.map((e) => ({ text: e.text, context: e.context, verdict: e.verdict })));
    onPage = new Map(entries.map((e, i) => [e.index, found[i] === true]));
    const hits = found.filter(Boolean).length;
    setHighlightNote(
      hits === 0
        ? 'None of these claims appear word for word on this page, so nothing was highlighted.'
        : `Highlighted ${hits} of ${entries.length} on this page. The rest were reworded or are not on it.`,
    );
  } catch (err) {
    onPage = null;
    setHighlightNote(
      err instanceof page.PageAccessError
        ? 'Chrome does not let extensions read this page, so nothing was highlighted.'
        : 'Could not highlight on this page.',
    );
  }
  renderAll();
}

async function clearOnPage(): Promise<void> {
  try {
    await page.clear();
  } catch {
    /* page navigated away or became unreadable: nothing left to clear */
  }
  onPage = null;
  setHighlightNote('');
  renderAll();
}

async function showOnPage(index: number): Promise<void> {
  try {
    const ok = await page.scrollTo(index);
    if (!ok) setHighlightNote('That claim is no longer highlighted. Highlight the page again.');
  } catch {
    setHighlightNote('Could not reach the page. It may have been closed or navigated away.');
  }
}

/* ---------- history ---------- */

async function renderHistory(): Promise<void> {
  const list = await loadHistory();
  clearOutput();
  headEl = null;
  slotEls = [];

  const back = h('button', { type: 'button', class: 'link' }, 'Back');
  back.addEventListener('click', () => {
    if (state.slots.length > 0) buildList();
    else renderIdle();
  });

  const head = h('div', { class: 'summary' }, h('h2', {}, 'History'));
  els.output.append(head, h('div', { class: 'row' }, back));

  if (list.length === 0) {
    els.output.append(h('p', { class: 'hint' }, 'Finished checks are kept here on this device, newest first.'));
    return;
  }

  const clearAll = h('button', { type: 'button', class: 'link' }, 'Clear all');
  clearAll.addEventListener('click', async () => {
    await saveHistory([]);
    void renderHistory();
  });
  els.output.append(h('div', { class: 'row' }, clearAll));

  const ul = h('ul', { class: 'history', 'aria-label': 'Past checks' });
  for (const entry of list) ul.append(historyItem(entry));
  els.output.append(ul);
}

function historyItem(entry: HistoryEntry): HTMLElement {
  const open = h('button', { type: 'button', class: 'history-open' },
    h('span', { class: 'history-preview' }, entry.preview || 'Untitled check'),
    h('span', { class: 'history-meta' },
      `${entry.results.length} ${entry.results.length === 1 ? 'claim' : 'claims'}, ${relativeTime(entry.at, Date.now())}`),
  );
  open.addEventListener('click', () => openEntry(entry));

  const remove = h('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Remove from history', title: 'Remove' }, '×');
  remove.addEventListener('click', async () => {
    await saveHistory(removeEntry(await loadHistory(), entry.id));
    void renderHistory();
  });
  return h('li', { class: 'history-item' }, open, remove);
}

function openEntry(entry: HistoryEntry): void {
  lastText = entry.preview;
  state = {
    ...initialState(),
    done: true,
    slots: entry.results.map((result) => ({
      status: 'done', id: result.claim.id, text: result.claim.original_text, result,
    })),
  };
  buildList();
  setHighlightNote('Saved result. Run a new check to refresh it.');
}

/* ---------- actions ---------- */

async function runAnalysis(): Promise<void> {
  const text = els.input.value.trim();
  if (!text) return;
  if (inFlight) inFlight.abort();

  inFlight = new AbortController();
  const mine = inFlight;
  lastText = text;
  els.analyze.textContent = 'Checking';
  updateCount();
  state = initialState();
  headEl = null;
  slotEls = [];
  onPage = null;
  renderLoading();
  void setBadge(WORKING, tabId);
  // A new check replaces whatever was highlighted for the previous one.
  void page.clear().catch(() => undefined);

  try {
    await analyzeStream(backend, text, onStreamEvent, mine.signal);
    void refreshHealth();
  } catch (err) {
    const e = err instanceof BackendError ? err : new BackendError('http', String(err));
    if (inFlight !== mine) return; // superseded by a newer check
    const partial = state.slots.length > 0;
    if (partial) {
      // Some claims are already on screen: keep them and mark the rest as failed.
      failPending(e.kind, e.kind === 'cancelled' ? 'Cancelled.' : e.message);
      finishBadge();
    } else if (e.kind === 'cancelled') {
      renderIdle();
      void setBadge(CLEARED, tabId);
    } else if (e.kind === 'offline') {
      setStatus('offline', 'Backend not running');
      renderOffline();
      void setBadge(FAILED, tabId);
    } else if (e.kind === 'timeout') {
      renderNotice('That took too long', 'The backend didn’t answer in time. Try a shorter passage.');
      void setBadge(FAILED, tabId);
    } else {
      renderNotice('The backend hit a problem', e.message);
      void setBadge(FAILED, tabId);
    }
  } finally {
    if (inFlight === mine) {
      inFlight = null;
      els.analyze.textContent = 'Check evidence';
      updateCount();
    }
  }
}

async function saveBackend(): Promise<void> {
  const normalized = normalizeBackendUrl(els.backendUrl.value);
  if (!normalized) {
    els.backendMsg.textContent = 'Use an address like http://127.0.0.1:8000. Only local addresses are allowed.';
    return;
  }
  backend = normalized;
  els.backendUrl.value = normalized;
  await setBackendUrl(normalized);
  els.backendMsg.textContent = 'Saved.';
  await refreshHealth();
}

/* ---------- hand-off from the context menu / shortcut ---------- */

async function consumePending(): Promise<void> {
  try {
    const stored = await chrome.storage.session.get(PENDING_KEY);
    const value = stored[PENDING_KEY];
    if (value === undefined) return;
    await chrome.storage.session.remove(PENDING_KEY);
    if (isFresh(value, Date.now())) {
      setInput(value.text);
      void runAnalysis();
    }
  } catch {
    /* storage.session unavailable: nothing was handed off */
  }
}

/* ---------- boot ---------- */

async function boot(): Promise<void> {
  els.input.maxLength = MAX_CHARS;
  els.input.addEventListener('input', () => {
    updateCount();
    saveDraft();
  });
  els.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void runAnalysis();
    }
  });
  els.analyze.addEventListener('click', () => void runAnalysis());
  els.grab.addEventListener('click', () => void useSelection(false));
  els.saveBackend.addEventListener('click', () => void saveBackend());
  els.historyBtn.addEventListener('click', () => void renderHistory());
  els.research.addEventListener('change', () => {
    research = els.research.checked;
    chrome.storage.local.set({ [RESEARCH_KEY]: research }).catch(() => undefined);
    renderAll();
  });
  els.theme.addEventListener('change', () => {
    applyTheme(els.theme.value);
    chrome.storage.local.set({ [THEME_KEY]: els.theme.value }).catch(() => undefined);
  });
  els.panel.addEventListener('click', async () => {
    try {
      const win = await chrome.windows.getCurrent();
      await chrome.sidePanel.open({ windowId: win.id as number });
      window.close();
    } catch {
      renderNotice('Side panel unavailable', 'This version of Chrome can’t open the side panel from here.');
    }
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'session' && changes[PENDING_KEY]?.newValue !== undefined) void consumePending();
  });

  renderIdle();
  updateCount();
  void detectSidePanel();

  backend = await getBackendUrl();
  els.backendUrl.value = backend;

  try {
    const [active] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    tabId = active?.id;
    const stored = await chrome.storage.local.get([DRAFT_KEY, RESEARCH_KEY, THEME_KEY]);
    if (typeof stored[DRAFT_KEY] === 'string') els.input.value = stored[DRAFT_KEY];
    research = stored[RESEARCH_KEY] === true;
    els.research.checked = research;
    const theme = typeof stored[THEME_KEY] === 'string' ? stored[THEME_KEY] : 'system';
    els.theme.value = ['light', 'dark'].includes(theme) ? theme : 'system';
    applyTheme(els.theme.value);
  } catch {
    /* no saved settings */
  }
  updateCount();

  const handedOff = chrome.storage.session
    .get(PENDING_KEY)
    .then((s) => s[PENDING_KEY] !== undefined)
    .catch(() => false);
  if (await handedOff) {
    await consumePending();
  } else if (!els.input.value.trim()) {
    await useSelection(true);
  }
  void refreshHealth();
}

void boot();
