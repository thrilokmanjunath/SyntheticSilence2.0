import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toJson, toMarkdown } from '../dist/export.js';
import { addEntry, compact, makeEntry, MAX_ENTRIES, relativeTime, removeEntry } from '../dist/history.js';
import { badgeFor } from '../dist/badge.js';
import { handleMenuClick, handleShortcut, isFresh, makePending, MAX_AGE_MS, PENDING_KEY } from '../dist/handoff.js';
import { kindFor } from '../dist/page.js';

const result = (over = {}) => ({
  claim: { id: 'c1', original_text: 'Honey never spoils.', context: 'Honey never spoils, they say.' },
  signal: { evidence_coverage: 1, semantic_support: 1, contradiction_level: 0, calibration_status: 'NOT_CALIBRATED' },
  explanation: 'Archaeologists found edible honey.',
  verdict: 'supported',
  leaning: null,
  sources_considered: 2,
  sources_relevant: 1,
  evidence: [
    { id: 'a', title: 'Honey [bee] *product*', text: 'x'.repeat(900), source_url: 'https://en.wikipedia.org/?curid=1',
      publication_year: null, kind: 'encyclopedia', stance: 'supports', confidence: 0.9, quote: 'edible after 3000 years' },
    { id: 'b', title: null, text: 'Unrelated text', source_url: null, publication_year: 2020, kind: 'scholarly',
      stance: 'irrelevant', confidence: 0.2, quote: null },
  ],
  ...over,
});

const ctx = { checkedAt: new Date('2026-10-13T12:30:00Z') };

/* ---------- export ---------- */

test('markdown: verdict headline, basis, explanation, sources with stance and quote', () => {
  const md = toMarkdown([result()], ctx);
  assert.match(md, /^# Evidence check/);
  assert.match(md, /Checked 2026-10-13 12:30 UTC/);
  assert.match(md, /## 1\. Honey never spoils\./);
  assert.match(md, /\*\*Sources back this up\*\*/);
  assert.match(md, /\(1 of 2 sources relevant\)/);
  assert.match(md, /Archaeologists found edible honey\./);
  assert.match(md, /- Supports: \[Honey \\\[bee\\\] \\\*product\\\*\]\(https:\/\/en\.wikipedia\.org\/\?curid=1\)/);
  assert.match(md, /  > edible after 3000 years/);
  assert.match(md, /- Unrelated: Unrelated text \(2020\)/);
  assert.ok(md.endsWith('\n'));
});

test('markdown: claim text cannot inject markdown structure', () => {
  const md = toMarkdown([result({ claim: { id: 'c', original_text: '# Bad\n[x](javascript:alert(1))', context: '' } })], ctx);
  assert.doesNotMatch(md, /^# Bad/m);
  assert.doesNotMatch(md, /\[x\]\(javascript/);
});

test('markdown: no sources and missing verdict fall back sensibly', () => {
  const md = toMarkdown([result({ verdict: undefined, evidence: [], sources_considered: 0, sources_relevant: 0 })], ctx);
  assert.match(md, /Sources don.t settle it/);
  assert.doesNotMatch(md, /Sources:/);
});

test('json export keeps results and a timestamp', () => {
  const parsed = JSON.parse(toJson([result()], ctx));
  assert.equal(parsed.checked_at, '2026-10-13T12:30:00.000Z');
  assert.equal(parsed.results[0].claim.original_text, 'Honey never spoils.');
});

/* ---------- history ---------- */

test('compact trims source text and drops claim context', () => {
  const [c] = compact([result()]);
  assert.equal(c.evidence[0].text.length, 400);
  assert.equal(c.claim.context, '');
  assert.equal(c.evidence[0].quote, 'edible after 3000 years');
});

test('addEntry: newest first, same text replaces, capped', () => {
  let list = [];
  list = addEntry(list, makeEntry('first text', [result()], 1, 'a'));
  list = addEntry(list, makeEntry('second text', [result()], 2, 'b'));
  list = addEntry(list, makeEntry('first text', [result()], 3, 'c'));
  assert.deepEqual(list.map((e) => e.id), ['c', 'b']);

  for (let i = 0; i < MAX_ENTRIES + 5; i += 1) list = addEntry(list, makeEntry(`t${i}`, [result()], 10 + i, `n${i}`));
  assert.equal(list.length, MAX_ENTRIES);
  assert.equal(list[0].id, `n${MAX_ENTRIES + 4}`);
});

test('addEntry: byte budget drops oldest entries', () => {
  const big = result({ evidence: Array.from({ length: 6 }, (_, i) => ({ id: `${i}`, text: 'y'.repeat(400), kind: 'scholarly' })) });
  let list = [];
  for (let i = 0; i < MAX_ENTRIES; i += 1) {
    list = addEntry(list, makeEntry(`t${i}`, Array.from({ length: 40 }, () => big), i, `n${i}`));
  }
  assert.ok(JSON.stringify(list).length <= 3_000_000);
  assert.equal(list[0].id, `n${MAX_ENTRIES - 1}`);
});

test('removeEntry and relativeTime', () => {
  const list = [makeEntry('a', [], 1, 'x'), makeEntry('b', [], 2, 'y')];
  assert.deepEqual(removeEntry(list, 'x').map((e) => e.id), ['y']);
  const now = 10_000_000;
  assert.equal(relativeTime(now - 5_000, now), 'just now');
  assert.equal(relativeTime(now - 5 * 60_000, now), '5 min ago');
  assert.equal(relativeTime(now - 3 * 3_600_000, now), '3 h ago');
  assert.equal(relativeTime(now - 24 * 3_600_000, now), 'yesterday');
  assert.equal(relativeTime(now - 4 * 86_400_000, now), '4 days ago');
});

test('makeEntry collapses whitespace and limits the preview', () => {
  const e = makeEntry('  hello\n\n   world  ' + 'z'.repeat(500), [], 5, 'id');
  assert.ok(e.preview.startsWith('hello world'));
  assert.equal(e.preview.length, 160);
});

/* ---------- badge ---------- */

test('badge colour follows the most serious verdict', () => {
  assert.deepEqual(badgeFor([]), { text: '', color: '#4E5D6C' });
  assert.deepEqual(badgeFor(['supported', 'supported']), { text: '2', color: '#0E8A8C' });
  assert.deepEqual(badgeFor(['supported', 'refuted']), { text: '2', color: '#C03A5B' });
  assert.deepEqual(badgeFor(['supported', 'mixed']), { text: '2', color: '#4E5D6C' });
  assert.equal(badgeFor(new Array(120).fill('supported')).text, '99+');
});

/* ---------- hand-off ---------- */

function fakeDeps({ selection = '', failRead = false, now = 1_000_000 } = {}) {
  const calls = [];
  return {
    calls,
    deps: {
      openPanel: async (t) => { calls.push(['open', t]); },
      store: async (k, v) => { calls.push(['store', k, v]); },
      readSelection: async (id) => { calls.push(['read', id]); if (failRead) throw new Error('blocked'); return selection; },
      now: () => now,
    },
  };
}

test('makePending trims and rejects empty', () => {
  assert.deepEqual(makePending('  hi  ', 5), { text: 'hi', at: 5 });
  assert.equal(makePending('   ', 5), null);
  assert.equal(makePending(undefined, 5), null);
});

test('isFresh: age window and shape', () => {
  assert.equal(isFresh({ text: 'x', at: 1000 }, 1000 + MAX_AGE_MS), true);
  assert.equal(isFresh({ text: 'x', at: 1000 }, 1000 + MAX_AGE_MS + 1), false);
  assert.equal(isFresh({ text: 'x', at: 5000 }, 1000), false);          // from the future
  assert.equal(isFresh({ text: '  ', at: 1000 }, 1000), false);
  assert.equal(isFresh('nope', 1000), false);
  assert.equal(isFresh(null, 1000), false);
});

test('menu click opens the panel first, then stores the selection', async () => {
  const { calls, deps } = fakeDeps();
  const outcome = await handleMenuClick('Honey never spoils.', { id: 7, windowId: 2 }, deps);
  assert.equal(outcome, 'queued');
  assert.deepEqual(calls.map((c) => c[0]), ['open', 'store']);
  assert.deepEqual(calls[0][1], { tabId: 7, windowId: 2 });
  assert.equal(calls[1][1], PENDING_KEY);
  assert.deepEqual(calls[1][2], { text: 'Honey never spoils.', at: 1_000_000 });
});

test('menu click: empty selection opens the panel but stores nothing', async () => {
  const { calls, deps } = fakeDeps();
  assert.equal(await handleMenuClick('   ', { id: 7 }, deps), 'empty');
  assert.deepEqual(calls.map((c) => c[0]), ['open']);
});

test('menu click: a failing openPanel does not lose the selection', async () => {
  const { calls, deps } = fakeDeps();
  deps.openPanel = async () => { throw new Error('no gesture'); };
  assert.equal(await handleMenuClick('text', { id: 1 }, deps), 'queued');
  assert.equal(calls.at(-1)[0], 'store');
});

test('menu click without a tab does nothing', async () => {
  const { calls, deps } = fakeDeps();
  assert.equal(await handleMenuClick('text', undefined, deps), 'no_tab');
  assert.equal(calls.length, 0);
});

test('shortcut reads the selection from the page', async () => {
  const { calls, deps } = fakeDeps({ selection: ' Water boils at 100C. ' });
  assert.equal(await handleShortcut({ id: 3, windowId: 1 }, deps), 'queued');
  assert.deepEqual(calls.map((c) => c[0]), ['open', 'read', 'store']);
  assert.equal(calls.at(-1)[2].text, 'Water boils at 100C.');
});

test('shortcut on an unreadable page still opens the panel', async () => {
  const { calls, deps } = fakeDeps({ failRead: true });
  assert.equal(await handleShortcut({ id: 3 }, deps), 'unreadable');
  assert.deepEqual(calls.map((c) => c[0]), ['open', 'read']);
});

test('shortcut with nothing selected stores nothing', async () => {
  const { calls, deps } = fakeDeps({ selection: '' });
  assert.equal(await handleShortcut({ id: 3 }, deps), 'empty');
  assert.equal(calls.some((c) => c[0] === 'store'), false);
});

/* ---------- page bridge ---------- */

test('highlight kinds map from verdicts', () => {
  assert.equal(kindFor('supported'), 'supported');
  assert.equal(kindFor('refuted'), 'refuted');
  assert.equal(kindFor('mixed'), 'mixed');
  assert.equal(kindFor('insufficient'), 'neutral');
  assert.equal(kindFor('no_sources'), 'neutral');
});
