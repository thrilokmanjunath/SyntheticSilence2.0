// Real-Chrome end-to-end check of the unpacked extension.
//
//   npm run e2e                  # deterministic: a stub backend, no network, no cost
//   npm run e2e -- --live        # smoke test against the real backend on 127.0.0.1:8000
//   npm run e2e -- --shots DIR   # also write light/dark screenshots of the results view
//
// Chrome 137+ ignores --load-extension on branded builds, so the extension is loaded with the
// CDP command Extensions.loadUnpacked over --remote-debugging-pipe (needs --enable-unsafe-extension-debugging).
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const live = process.argv.includes('--live');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ].filter(Boolean);
  const found = candidates.find((c) => existsSync(c));
  if (!found) throw new Error('Chrome not found. Set CHROME_PATH.');
  return found;
}

// ---- fixtures ----
const source = (over) => ({ id: 'x', text: '', title: null, source_url: null, publication_year: null,
  kind: 'encyclopedia', stance: null, confidence: null, quote: null, relevance: 0.5, ...over });
const signal = (over) => ({ evidence_coverage: 1, semantic_support: 0, retrieval_confidence: 0.3, contradiction_level: 0,
  temporal_coverage: 0, representation_density: 0.8, uncertainty: 0.6, insufficiency_signal: 0.7,
  construction_family_estimate: 'ambiguous_claim', calibration_status: 'NOT_CALIBRATED', ...over });

const CLAIM_1 = 'Water boils at 100 degrees Celsius at sea level.';
const CLAIM_2 = 'The United Nations Charter was drafted in 1946.';
const CLAIM_3 = 'Zorblax is the capital of Atlantis.';

const FIXTURE = {
  truncated: false,
  results: [
    {
      claim: { id: 'c1', original_text: CLAIM_1, context: '' },
      signal: signal({ semantic_support: 1 }),
      explanation: 'Two encyclopedia entries state the boiling point.',
      verdict: 'supported', leaning: null, sources_considered: 3, sources_relevant: 2,
      evidence: [
        source({ id: 'a', title: 'Boiling point', source_url: 'https://en.wikipedia.org/?curid=1',
          text: 'The boiling point of water is 100 degrees Celsius at sea level.', stance: 'supports', confidence: 0.95,
          quote: 'boiling point of water is 100 degrees Celsius' }),
        source({ id: 'b', title: 'Water', source_url: 'https://en.wikipedia.org/?curid=2',
          text: 'Water boils at 100 degrees Celsius under standard pressure.', stance: 'supports', confidence: 0.9,
          quote: 'boils at 100 degrees Celsius' }),
        source({ id: 'c', title: 'Ferrets', text: 'Ferrets are domesticated mammals.', stance: 'irrelevant', confidence: 0.9 }),
      ],
    },
    {
      claim: { id: 'c2', original_text: CLAIM_2, context: '' },
      signal: signal({ semantic_support: 0.5, contradiction_level: 0.5 }),
      explanation: 'Sources disagree on the date.',
      verdict: 'mixed', leaning: null, sources_considered: 2, sources_relevant: 2,
      evidence: [
        source({ id: 'd', title: 'United Nations', text: 'Established by the signing of the Charter on 26 June 1945.',
          stance: 'refutes', confidence: 0.9, quote: 'signing of the Charter on 26 June 1945' }),
        source({ id: 'e', title: 'UN Charter', text: 'The Charter entered into force in 1946 after ratification.',
          stance: 'supports', confidence: 0.7, quote: 'entered into force in 1946' }),
      ],
    },
    {
      claim: { id: 'c3', original_text: CLAIM_3, context: '' },
      signal: signal({ evidence_coverage: 0 }),
      explanation: 'No sources were found.',
      verdict: 'no_sources', leaning: null, sources_considered: 0, sources_relevant: 0, evidence: [],
    },
  ],
};

// A real page: claim 1 split across inline tags, claim 2 with different case, claim 3 only in a hidden node.
const PAGE_HTML = `<!doctype html><html><head><meta charset="utf-8"><title>Fixture article</title></head><body>
<h1>Fixture article</h1>
<p id="sel">Water boils at <b>100 degrees</b> Celsius at sea level.</p>
<div style="height:1800px">spacer</div>
<p id="two">Historians note that THE UNITED NATIONS CHARTER was drafted in 1946, after the war.</p>
<div style="display:none">Zorblax is the capital of Atlantis.</div>
</body></html>`;

const stats = { stream: 0, health: 0 };

function startStub() {
  const server = createServer((req, res) => {
    const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'content-type' };
    if (req.method === 'OPTIONS') { res.writeHead(204, cors).end(); return; }
    if (req.url === '/page.html') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(PAGE_HTML);
    } else if (req.url === '/health') {
      stats.health += 1;
      res.writeHead(200, { ...cors, 'content-type': 'application/json' });
      res.end(JSON.stringify({ status: 'healthy', pipeline_ready: true, pipeline_error: null,
        info: { verdict_mode: 'pooled', retrievers: ['wikipedia', 'openalex'], openalex_key: false, model: 'm', cache: true } }));
    } else if (req.url === '/api/v1/analyze/stream' && req.method === 'POST') {
      stats.stream += 1;
      let body = '';
      req.on('data', (c) => { body += c; });
      req.on('end', () => {
        const text = JSON.parse(body).source_text;
        const send = (obj) => res.write(JSON.stringify(obj) + '\n');
        res.writeHead(200, { ...cors, 'content-type': 'application/x-ndjson' });

        // Nothing could be analysed (for example the LLM account is out of credit).
        if (text.includes('FATAL')) {
          send({ type: 'error', error: { kind: 'llm', message: 'The language model account is out of credit (402).' } });
          res.end();
          return;
        }
        // The connection drops after the claims were announced, without a terminal line.
        if (text.includes('DROPPED')) {
          send({ type: 'claims', claims: [FIXTURE.results[0].claim, FIXTURE.results[1].claim], truncated: false });
          setTimeout(() => {
            send({ type: 'claim', index: 0, result: FIXTURE.results[0] });
            res.end();
          }, 200);
          return;
        }

        // A single known claim (retry, or a hand-off): answer with that claim's fixture result.
        const single = FIXTURE.results.findIndex((r) => r.claim.original_text === text.trim());
        if (single !== -1) {
          send({ type: 'claims', claims: [FIXTURE.results[single].claim], truncated: false });
          setTimeout(() => {
            send({ type: 'claim', index: 0, result: FIXTURE.results[single] });
            send({ type: 'done' });
            res.end();
          }, 150);
          return;
        }

        // Full run: claims first, then results out of order, one claim failing on its own.
        send({ type: 'claims', claims: FIXTURE.results.map((r) => r.claim), truncated: false });
        setTimeout(() => send({ type: 'claim', index: 2, result: FIXTURE.results[2] }), 600);
        setTimeout(() => send({ type: 'claim', index: 0, result: FIXTURE.results[0] }), 900);
        setTimeout(() => {
          send({ type: 'claim_error', index: 1,
            error: { kind: 'retrieval_budget', message: 'OpenAlex search budget is used up (resets in about 10h).' } });
          send({ type: 'done' });
          res.end();
        }, 1200);
      });
    } else {
      res.writeHead(404, cors).end();
    }
  });
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r(server)));
}

// ---- Chrome over a debugging pipe ----
const profile = mkdtempSync(join(tmpdir(), 'ss-e2e-'));
const chrome = spawn(
  findChrome(),
  [`--user-data-dir=${profile}`, '--remote-debugging-pipe', '--enable-unsafe-extension-debugging',
    '--headless=new', '--no-first-run', '--no-default-browser-check', 'about:blank'],
  { stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'] },
);
let nextId = 0;
const pending = new Map();
const events = [];
let buf = '';
chrome.stdio[4].on('data', (d) => {
  buf += d.toString('utf8');
  let i;
  while ((i = buf.indexOf('\0')) >= 0) {
    const msg = JSON.parse(buf.slice(0, i));
    buf = buf.slice(i + 1);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method) events.push(msg);
  }
});
const send = (method, params = {}, sessionId) => new Promise((resolve_, reject) => {
  const id = ++nextId;
  const t = setTimeout(() => reject(new Error(`timeout: ${method}`)), 30000);
  pending.set(id, (m) => { clearTimeout(t); m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve_(m.result); });
  chrome.stdio[3].write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + '\0');
});

async function attach(targetId) {
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const call = (m, p) => send(m, p, sessionId);
  const evaluate = async (expression) => {
    const r = await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails.exception?.description ?? r.exceptionDetails));
    return r.result.value;
  };
  const waitFor = async (expr, label, ms = 60000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) {
      if (await evaluate(expr)) return;
      await sleep(150);
    }
    throw new Error(`timed out waiting for ${label}`);
  };
  return { sessionId, call, evaluate, waitFor };
}

const checks = [];
const check = (name, fn) => checks.push([name, fn]);
let errorsSoFar = null;
let stub = null;
let exitCode = 0;
const json = (v) => JSON.stringify(v);

try {
  let backend = 'http://127.0.0.1:8000';
  if (!live) {
    stub = await startStub();
    backend = `http://127.0.0.1:${stub.address().port}`;
  }

  const { id: extId } = await send('Extensions.loadUnpacked', { path: root });
  const origin = `chrome-extension://${extId}`;

  // ---- service worker: context menu and shortcut are registered ----
  let swTarget;
  for (let i = 0; i < 40 && !swTarget; i += 1) {
    const { targetInfos } = await send('Target.getTargets');
    swTarget = targetInfos.find((t) => t.type === 'service_worker' && t.url === `${origin}/dist/background.js`);
    if (!swTarget) await sleep(250);
  }
  check('service worker is running', () => assert.ok(swTarget, 'background service worker not found'));
  if (swTarget) {
    const sw = await attach(swTarget.targetId);
    const dup = await sw.evaluate(`new Promise((res) => {
      chrome.contextMenus.create({ id: 'ss-check-selection', title: 'probe', contexts: ['selection'] },
        () => res(chrome.runtime.lastError ? chrome.runtime.lastError.message : 'created'));
    })`);
    check('context menu item exists', () => assert.match(dup, /duplicate id/i, dup));
    const cmds = JSON.parse(await sw.evaluate(`chrome.commands.getAll().then((c) => JSON.stringify(c))`));
    check('keyboard shortcut is declared', () => {
      const c = cmds.find((x) => x.name === 'check-selection');
      assert.ok(c, json(cmds));
      assert.equal(c.shortcut, 'Alt+Shift+S');
    });
  }

  // ---- the page we will read selections from and highlight on ----
  let articleUrl = `${backend}/page.html`;
  let article = null;
  if (!live) {
    const { targetId: pageTarget } = await send('Target.createTarget', { url: articleUrl });
    article = await attach(pageTarget);
    await article.call('Runtime.enable');
    await article.waitFor(`document.readyState === 'complete'`, 'article page');
  }

  // ---- the popup / panel page ----
  const { targetId } = await send('Target.createTarget', { url: `${origin}/popup.html` });
  const popup = await attach(targetId);
  const { sessionId } = popup;
  await popup.call('Runtime.enable');
  await popup.call('Log.enable');
  // Make the article the active tab, as it is when a user opens the popup from it.
  if (article) await send('Target.activateTarget', { targetId: article.sessionId ? (await send('Target.getTargets')).targetInfos.find((t) => t.url === articleUrl).targetId : '' });

  const { evaluate, waitFor, call: page } = popup;

  // Point the popup at the backend under test, then reload so it boots with that address.
  await sleep(500);
  await evaluate(`chrome.storage.local.set({ backendUrl: ${json(backend)}, draft: '', researchMode: false, theme: 'system', history: [] })`);
  await page('Page.reload');
  await sleep(500);
  // The very first boot probes the default address before it is repointed; ignore its console output.
  const eventsBaseline = events.length;
  await waitFor(`document.getElementById('status')?.dataset.state === 'ready'`, 'backend ready');

  const apis = JSON.parse(await evaluate(`JSON.stringify({ storage: typeof chrome.storage?.local?.get,
    session: typeof chrome.storage?.session?.get, scripting: typeof chrome.scripting?.executeScript,
    sidePanel: typeof chrome.sidePanel?.open, getContexts: typeof chrome.runtime?.getContexts,
    badge: typeof chrome.action?.setBadgeText })`));
  check('chrome APIs available', () => assert.ok(Object.values(apis).every((v) => v === 'function'), json(apis)));

  if (!live) {
    const info = await evaluate(`document.getElementById('backendInfo').textContent`);
    check('backend configuration is shown', () => assert.match(info, /pooled score; sources: wikipedia, openalex/));

    // ---- real page selection ----
    await article.evaluate(`window.getSelection().selectAllChildren(document.getElementById('sel')); true`);
    await evaluate(`document.getElementById('grabBtn').click()`);
    await waitFor(`document.getElementById('inputText').value.includes('Water boils')`, 'selection grabbed');
    const grabbed = await evaluate(`document.getElementById('inputText').value`);
    check('Use page selection reads the real selection', () => assert.equal(grabbed, CLAIM_1));
  }

  const text = live
    ? 'Water boils at 100 degrees Celsius at sea level. The Great Wall of China is visible from space with the naked eye.'
    : [CLAIM_1, CLAIM_2, CLAIM_3].join(' ');
  await evaluate(`(() => { const t = document.getElementById('inputText'); t.value = ${json(text)};
    t.dispatchEvent(new Event('input', { bubbles: true })); document.getElementById('analyzeBtn').click(); })()`);
  await waitFor(`document.querySelectorAll('.claim').length > 0`, 'results');

  // Claims are announced before any result: the first paint shows pending rows with the claim text.
  const early = JSON.parse(await evaluate(`JSON.stringify({
    pending: document.querySelectorAll('.claim.is-pending').length,
    progress: document.querySelector('.summary')?.innerText ?? '' })`));
  if (!live) {
    check('claims appear pending before results arrive', () => {
      assert.ok(early.pending >= 1, json(early));
      assert.match(early.progress, /finished/);
    });
  }
  await waitFor(`document.querySelectorAll('.claim.is-pending').length === 0`, 'stream to finish');

  const readClaims = `JSON.stringify([...document.querySelectorAll('.claim')].map((el) => ({
    verdict: el.dataset.verdict,
    claim: el.querySelector('blockquote').textContent,
    headline: el.querySelector('.verdict').textContent,
    basis: el.querySelector('.basis')?.textContent ?? null,
    support: el.querySelectorAll('.seg.support').length,
    conflict: el.querySelectorAll('.seg.conflict').length,
    sources: el.querySelectorAll('.source').length,
    chips: [...el.querySelectorAll('.chip')].map((c) => c.textContent),
    marks: [...el.querySelectorAll('.src-text mark')].map((m) => m.textContent),
    filters: [...el.querySelectorAll('.filter')].map((f) => f.textContent),
  })))`;
  const claims = JSON.parse(await evaluate(readClaims));
  console.log(json(claims));

  if (!live) {
    check('three claims render', () => assert.equal(claims.length, 3));
    check('supported claim', () => {
      assert.equal(claims[0].headline, 'Sources back this up');
      assert.equal(claims[0].basis, '2 of 3 sources are relevant');
      assert.equal(claims[0].support, 20);
      assert.deepEqual(claims[0].chips, ['Supports 95%', 'Supports 90%', 'Unrelated']);
      assert.ok(claims[0].marks.includes('boiling point of water is 100 degrees Celsius'));
    });
    check('a failing claim is an explicit error row, not silence', () => {
      assert.equal(claims[1].headline, 'Couldn\u2019t check this claim');
      assert.equal(claims[1].verdict, undefined);
      assert.equal(claims[1].support + claims[1].conflict, 0);
    });
    check('no-source claim is silent', () => {
      assert.equal(claims[2].headline, 'No sources found');
      assert.equal(claims[2].support + claims[2].conflict, 0);
    });
    const summaryText = await evaluate(`document.querySelector('.summary').innerText`);
    check('summary counts the failed claim', () => assert.match(summaryText, /3 claims found[\s\S]*1 couldn.t be checked/));

    // Retry just the failed claim; the others must stay as they were.
    await evaluate(`document.querySelector('.claim.is-error .link').click()`);
    await waitFor(`document.querySelectorAll('.claim')[1]?.dataset.verdict === 'mixed'`, 'retried claim');
    const retried = JSON.parse(await evaluate(`JSON.stringify({
      headline: document.querySelectorAll('.claim')[1].querySelector('.verdict').textContent,
      support: document.querySelectorAll('.claim')[1].querySelectorAll('.seg.support').length,
      conflict: document.querySelectorAll('.claim')[1].querySelectorAll('.seg.conflict').length,
      filters: [...document.querySelectorAll('.claim')[1].querySelectorAll('.filter')].map((f) => f.textContent),
      first: document.querySelectorAll('.claim')[0].querySelector('.verdict').textContent,
      errors: document.querySelectorAll('.claim.is-error').length })`));
    check('retry fills only that claim, with both tones and filters', () => {
      assert.equal(retried.headline, 'Sources disagree');
      assert.ok(retried.support > 0 && retried.conflict > 0);
      assert.deepEqual(retried.filters, ['All', 'Supports', 'Disputes']);
      assert.equal(retried.first, 'Sources back this up');
      assert.equal(retried.errors, 0);
    });

    // ---- toolbar badge ----
    const activeTab = await evaluate(`chrome.tabs.query({ active: true, lastFocusedWindow: true }).then((t) => t[0]?.id)`);
    const badge = await evaluate(`chrome.action.getBadgeText({ tabId: ${activeTab} })`);
    check('toolbar badge shows the claim count', () => assert.equal(badge, '3'));

    // ---- research mode, filter ----
    const before = await evaluate(`document.querySelectorAll('.claim')[0].querySelectorAll('.metric').length`);
    await evaluate(`document.getElementById('researchMode').click()`);
    await sleep(300);
    const after = await evaluate(`document.querySelectorAll('.claim')[0].querySelectorAll('.metric').length`);
    check('research mode adds experimental metrics', () => assert.ok(after > before, `${before} -> ${after}`));

    await evaluate(`document.querySelectorAll('.claim')[1].querySelector('details').open = true;
      [...document.querySelectorAll('.claim')[1].querySelectorAll('.filter')].find((b) => b.textContent === 'Disputes').click()`);
    const visible = await evaluate(`[...document.querySelectorAll('.claim')[1].querySelectorAll('.source')]
      .filter((s) => getComputedStyle(s).display !== 'none').length`);
    check('filter hides non-matching sources', () => assert.equal(visible, 1));

    // ---- highlight on the real page ----
    await evaluate(`[...document.querySelectorAll('.actions button')].find((b) => b.textContent === 'Highlight on page').click()`);
    await waitFor(`(document.querySelector('#output .hint[role=status]')?.textContent ?? '').length > 0`, 'highlight note');
    const note = await evaluate(`document.querySelector('#output .hint[role=status]').textContent`);
    const hl = JSON.parse(await article.evaluate(`JSON.stringify({
      names: [...CSS.highlights.keys()].sort(),
      supported: [...(CSS.highlights.get('ss-supported') ?? [])].map((r) => r.toString()),
      mixed: [...(CSS.highlights.get('ss-mixed') ?? [])].map((r) => r.toString()),
      style: !!document.getElementById('ss-highlight-style') })`));
    check('highlight reports 2 of 3 found', () => assert.match(note, /Highlighted 2 of 3/));
    check('highlight spans inline tags and ignores case; hidden text is skipped', () => {
      assert.deepEqual(hl.names, ['ss-mixed', 'ss-supported']);
      // A trailing full stop is not part of the match, so the highlight ends at the last word.
      assert.deepEqual(hl.supported, ['Water boils at 100 degrees Celsius at sea level']);
      assert.deepEqual(hl.mixed, ['THE UNITED NATIONS CHARTER was drafted in 1946']);
      assert.equal(hl.style, true);
    });
    const notFound = await evaluate(`document.querySelectorAll('.claim')[2].innerText.includes('Not found on this page')`);
    check('claim missing from the page is labelled', () => assert.equal(notFound, true));

    await article.evaluate(`window.scrollTo(0, 0); true`);
    await evaluate(`document.querySelectorAll('.claim')[1].querySelector('.show-on-page').click()`);
    await sleep(900);
    const scrolled = await article.evaluate(`window.scrollY`);
    check('Show on page scrolls to the claim', () => assert.ok(scrolled > 300, `scrollY=${scrolled}`));

    await evaluate(`[...document.querySelectorAll('.actions button')].find((b) => b.textContent === 'Clear highlights').click()`);
    await sleep(300);
    const cleared = JSON.parse(await article.evaluate(`JSON.stringify({ n: CSS.highlights.size, style: !!document.getElementById('ss-highlight-style') })`));
    check('Clear highlights removes them and the style', () => assert.deepEqual(cleared, { n: 0, style: false }));

    // ---- export ----
    await evaluate(`window.__copied = null; navigator.clipboard.writeText = async (t) => { window.__copied = t; }`);
    await evaluate(`[...document.querySelectorAll('.actions button')].find((b) => b.textContent === 'Copy as Markdown').click()`);
    await sleep(200);
    const md = await evaluate(`window.__copied`);
    const mdLabel = await evaluate(`[...document.querySelectorAll('.actions button')].map((b) => b.textContent)`);
    check('Copy as Markdown copies a report', () => {
      assert.match(md, /^# Evidence check/);
      assert.match(md, /Sources back this up/);
      assert.match(md, /Zorblax is the capital of Atlantis\./);
      assert.ok(mdLabel.includes('Copied'), json(mdLabel));
    });
    await evaluate(`[...document.querySelectorAll('.actions button')].find((b) => b.textContent === 'Copy JSON').click()`);
    await sleep(200);
    const copiedJson = await evaluate(`window.__copied`);
    check('Copy JSON copies parseable results', () => {
      const parsed = JSON.parse(copiedJson);
      assert.equal(parsed.results.length, 3);
    });

    // ---- history ----
    const stored = await evaluate(`chrome.storage.local.get('history').then((s) => s.history.length)`);
    check('finished check is saved to history', () => assert.equal(stored, 1));
    const streamsBefore = stats.stream;
    await evaluate(`document.getElementById('historyBtn').click()`);
    await waitFor(`document.querySelectorAll('.history-item').length === 1`, 'history list');
    const histText = await evaluate(`document.querySelector('.history-open').innerText`);
    check('history lists the check', () => assert.match(histText, /Water boils at 100 degrees[\s\S]*3 claims/));
    await evaluate(`document.querySelector('.history-open').click()`);
    await waitFor(`document.querySelectorAll('.claim').length === 3`, 'saved result');
    const reopened = await evaluate(`document.querySelectorAll('.claim')[0].querySelector('.verdict').textContent`);
    const streamsAfter = stats.stream;
    check('opening history shows the saved verdicts without a new request', () => {
      assert.equal(reopened, 'Sources back this up');
      assert.equal(streamsAfter, streamsBefore);
    });
    await evaluate(`document.getElementById('historyBtn').click()`);
    await waitFor(`document.querySelector('.history-item .icon-btn')`, 'history again');
    await evaluate(`document.querySelector('.history-item .icon-btn').click()`);
    await waitFor(`document.querySelectorAll('.history-item').length === 0`, 'history emptied');
    const remaining = await evaluate(`chrome.storage.local.get('history').then((s) => s.history.length)`);
    check('history entries can be removed', () => assert.equal(remaining, 0));

    // ---- hand-off from the context menu / shortcut ----
    await evaluate(`chrome.storage.session.set({ pendingCheck: { text: ${json(CLAIM_1)}, at: Date.now() } })`);
    await waitFor(`document.querySelectorAll('.claim').length === 1 && document.querySelectorAll('.claim.is-pending').length === 0
      && document.getElementById('inputText').value === ${json(CLAIM_1)}`, 'hand-off check');
    const handed = await evaluate(`document.querySelector('.claim blockquote').textContent`);
    const left = await evaluate(`chrome.storage.session.get('pendingCheck').then((s) => 'pendingCheck' in s)`);
    check('hand-off runs the check and clears the request', () => {
      assert.equal(handed, CLAIM_1);
      assert.equal(left, false);
    });

    const runsBefore = stats.stream;
    await evaluate(`chrome.storage.session.set({ pendingCheck: { text: ${json(CLAIM_2)}, at: Date.now() - 10 * 60 * 1000 } })`);
    await sleep(800);
    const staleInput = await evaluate(`document.getElementById('inputText').value`);
    const runsAfter = stats.stream;
    check('a stale hand-off is ignored', () => {
      assert.equal(runsAfter, runsBefore);
      assert.equal(staleInput, CLAIM_1);
    });

    // ---- theme persists across reloads ----
    await evaluate(`(() => { const s = document.getElementById('theme'); s.value = 'dark'; s.dispatchEvent(new Event('change')); })()`);
    await sleep(200);
    await page('Page.reload');
    await waitFor(`document.documentElement.dataset.theme === 'dark'`, 'theme restored');
    const bg = await evaluate(`getComputedStyle(document.body).backgroundColor`);
    const researchKept = await evaluate(`document.getElementById('researchMode').checked`);
    check('dark theme applies and persists', () => assert.equal(bg, 'rgb(17, 23, 29)'));
    check('research mode persists', () => assert.equal(researchKept, true));

    // ---- fatal stream error: a clear message, not an empty result ----
    await evaluate(`(() => { const t = document.getElementById('inputText'); t.value = 'FATAL please';
      t.dispatchEvent(new Event('input', { bubbles: true })); document.getElementById('analyzeBtn').click(); })()`);
    await waitFor(`document.querySelector('.notice h2')`, 'fatal notice');
    const fatalText = await evaluate(`document.getElementById('output').innerText`);
    const fatalBadge = await evaluate(`chrome.action.getBadgeText({ tabId: ${activeTab} })`);
    check('a fatal backend error is explained', () => {
      assert.match(fatalText, /backend hit a problem/i);
      assert.match(fatalText, /out of credit/);
      assert.equal(fatalBadge, '!');
    });

    // ---- connection dropped mid-stream: kept results stay, the rest is marked failed ----
    await evaluate(`(() => { const t = document.getElementById('inputText'); t.value = 'DROPPED please';
      t.dispatchEvent(new Event('input', { bubbles: true })); document.getElementById('analyzeBtn').click(); })()`);
    await waitFor(`document.querySelectorAll('.claim').length === 2 && document.querySelectorAll('.claim.is-pending').length === 0`, 'dropped stream settled');
    const dropped = JSON.parse(await evaluate(`JSON.stringify({
      first: document.querySelectorAll('.claim')[0].querySelector('.verdict').textContent,
      second: document.querySelectorAll('.claim')[1].querySelector('.verdict').textContent,
      why: document.querySelectorAll('.claim')[1].querySelector('.why').textContent })`));
    check('a dropped connection keeps finished claims and fails the rest', () => {
      assert.equal(dropped.first, 'Sources back this up');
      assert.equal(dropped.second, 'Couldn’t check this claim');
      assert.match(dropped.why, /closed before the analysis finished/);
    });

    // Console errors so far; the offline step below fails requests on purpose.
    errorsSoFar = events.slice(eventsBaseline).filter((e) => e.sessionId === sessionId &&
      (e.method === 'Runtime.exceptionThrown' || (e.method === 'Log.entryAdded' && e.params.entry.level === 'error')));

    // ---- backend offline is an explicit state ----
    await evaluate(`chrome.storage.local.set({ backendUrl: 'http://127.0.0.1:9' })`);
    await page('Page.reload');
    await waitFor(`document.getElementById('status')?.dataset.state === 'offline'`, 'offline status');
    await evaluate(`document.getElementById('analyzeBtn').click()`);
    await waitFor(`document.querySelector('.notice h2')`, 'offline notice');
    const offline = await evaluate(`document.querySelector('.notice h2').textContent`);
    check('offline backend shows how to start it', () => assert.match(offline, /reach the backend/));
  } else {
    check('at least one claim renders', () => assert.ok(claims.length >= 1));
    check('every claim has a headline', () => assert.ok(claims.every((c) => c.headline)));
  }

  // ---- screenshots (optional) ----
  const shotsArg = process.argv.indexOf('--shots');
  if (shotsArg !== -1 && !live) {
    await evaluate(`chrome.storage.local.set({ backendUrl: ${json(backend)}, theme: 'system', researchMode: false })`);
    await page('Page.reload');
    await waitFor(`document.getElementById('status')?.dataset.state === 'ready'`, 'ready for shots');
    await evaluate(`(() => { const t = document.getElementById('inputText'); t.value = ${json(text)};
      t.dispatchEvent(new Event('input', { bubbles: true })); document.getElementById('analyzeBtn').click(); })()`);
    await waitFor(`document.querySelectorAll('.claim').length === 3 && document.querySelectorAll('.is-pending').length === 0`, 'shots results');
    const dir = resolve(process.argv[shotsArg + 1]);
    mkdirSync(dir, { recursive: true });
    await send('Target.activateTarget', { targetId }); // a background tab cannot be captured
    await evaluate(`document.querySelectorAll('.claim details').forEach((d) => { d.open = true; })`);
    const height = await evaluate(`document.documentElement.scrollHeight`);
    for (const scheme of ['light', 'dark']) {
      await page('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }] });
      await page('Emulation.setDeviceMetricsOverride', { width: 420, height, deviceScaleFactor: 1, mobile: false });
      await sleep(400);
      const shot = await page('Page.captureScreenshot', { format: 'png' });
      writeFileSync(join(dir, `popup-${scheme}.png`), Buffer.from(shot.data, 'base64'));
    }
    console.log(`screenshots in ${dir}`);
  }

  const errors = errorsSoFar ?? events.slice(eventsBaseline).filter((e) => e.sessionId === sessionId &&
    (e.method === 'Runtime.exceptionThrown' || (e.method === 'Log.entryAdded' && e.params.entry.level === 'error')));
  check('no console errors', () => assert.equal(errors.length, 0, json(errors.slice(0, 2))));

  for (const [name, fn] of checks) {
    try { await fn(); console.log(`ok   ${name}`); }
    catch (err) { exitCode = 1; console.log(`FAIL ${name}: ${err.message}`); }
  }
} catch (err) {
  console.error('E2E FAILED:', err.message);
  exitCode = 1;
} finally {
  chrome.kill();
  stub?.close();
  await sleep(800);
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* profile still locked */ }
  process.exit(exitCode);
}

