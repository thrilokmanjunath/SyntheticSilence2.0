import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildSegments, headlineFor, locateQuote, toClaimView, summarize, truncate, SEGMENTS } from '../dist/present.js';
import { normalizeBackendUrl } from '../dist/api.js';

const signal = (over = {}) => ({
  evidence_coverage: 1,
  semantic_support: 0.1,
  retrieval_confidence: 0.5,
  contradiction_level: 0.1,
  temporal_coverage: 0,
  representation_density: 0.4,
  uncertainty: 0.8,
  insufficiency_signal: 0.65,
  construction_family_estimate: 'ambiguous_claim',
  calibration_status: 'NOT_CALIBRATED',
  ...over,
});

const source = (over = {}) => ({
  id: 'e1',
  text: 'Honey found in ancient tombs was still edible after three thousand years.',
  source_url: 'https://example.org/a',
  publication_year: 2020,
  kind: 'scholarly',
  ...over,
});

const result = (over = {}) => ({
  claim: { id: 'c1', original_text: 'Honey never spoils.', context: '' },
  signal: signal(),
  explanation: 'Because.',
  evidence: [source()],
  verdict: 'insufficient',
  leaning: null,
  sources_considered: 1,
  sources_relevant: 1,
  ...over,
});

const count = (segs, tone) => segs.filter((t) => t === tone).length;

test('headlines per verdict, with leaning', () => {
  assert.equal(headlineFor('supported', null), 'Sources back this up');
  assert.equal(headlineFor('refuted', null), 'Sources push against this');
  assert.equal(headlineFor('mixed', null), 'Sources disagree');
  assert.equal(headlineFor('no_sources', null), 'No sources found');
  assert.equal(headlineFor('insufficient', 'supports'), 'Leans true, not settled');
  assert.equal(headlineFor('insufficient', 'refutes'), 'Leans false, not settled');
  assert.equal(headlineFor('insufficient', null), 'Sources don’t settle it');
});

test('segments: supported fills from the left with support', () => {
  const segs = buildSegments('supported', 0.8, 0);
  assert.equal(segs.length, SEGMENTS);
  assert.equal(count(segs, 'support'), 16);
  assert.equal(segs[0], 'support');
  assert.equal(segs[19], 'none');
});

test('segments: refuted is lit by conflict, not support', () => {
  const segs = buildSegments('refuted', 0, 1);
  assert.equal(count(segs, 'conflict'), SEGMENTS);
});

test('segments: mixed shows both sides and they never overwrite each other', () => {
  const segs = buildSegments('mixed', 0.6, 0.6);
  assert.equal(count(segs, 'support'), 12);
  assert.equal(count(segs, 'conflict'), 8); // only the room that is left
  assert.equal(segs[0], 'support');
  assert.equal(segs[19], 'conflict');
});

test('segments: no sources is fully silent', () => {
  assert.equal(count(buildSegments('no_sources', 1, 1), 'none'), SEGMENTS);
});

test('segments: insufficient leaning against shows conflict', () => {
  assert.equal(count(buildSegments('insufficient', 0.1, 0.5), 'conflict'), 10);
});

test('toClaimView: nulls and non-finite numbers do not throw', () => {
  const v = toClaimView(
    result({
      signal: signal({ retrieval_confidence: null, uncertainty: null, insufficiency_signal: null, temporal_coverage: null, semantic_support: Number.NaN }),
    }),
    { research: true },
  );
  assert.equal(v.verdict, 'insufficient');
  assert.equal(v.metrics.find((m) => m.key === 'gap').value, null);
});

test('toClaimView: experimental signals appear only in research mode', () => {
  const normal = toClaimView(result()).metrics.map((m) => m.key);
  const research = toClaimView(result(), { research: true }).metrics.map((m) => m.key);
  assert.deepEqual(normal, ['support', 'conflict', 'recent']);
  assert.ok(research.includes('gap') && research.includes('density') && research.includes('uncertainty'));
});

test('toClaimView: basis text and missing verdict fallback', () => {
  assert.equal(toClaimView(result({ sources_relevant: 2, sources_considered: 6 })).basis, '2 of 6 sources are relevant');
  assert.equal(toClaimView(result({ sources_relevant: 1, sources_considered: 1 })).basis, '1 of 1 source is relevant');
  const old = toClaimView(result({ verdict: undefined, evidence: [] , sources_considered: 0, sources_relevant: 0 }));
  assert.equal(old.verdict, 'no_sources');
  assert.equal(old.basis, null);
});

test('toClaimView: unsafe source URLs are dropped', () => {
  const v = toClaimView(result({ evidence: [source({ source_url: 'javascript:alert(1)' })] }));
  assert.equal(v.sources[0].url, null);
});

test('toClaimView: sources are ordered decisive first, by confidence', () => {
  const v = toClaimView(
    result({
      evidence: [
        source({ id: 'a', stance: 'irrelevant', confidence: 0.9 }),
        source({ id: 'b', stance: 'neutral', confidence: 0.7 }),
        source({ id: 'c', stance: 'refutes', confidence: 0.6, quote: 'still edible after three thousand years' }),
        source({ id: 'd', stance: 'supports', confidence: 0.9, quote: 'was still edible' }),
        source({ id: 'e', stance: 'supports', confidence: 0.7, quote: 'ancient tombs was' }),
      ],
    }),
  );
  assert.deepEqual(v.sources.map((s) => s.id), ['d', 'e', 'c', 'b', 'a']);
  assert.equal(v.sources[0].stanceLabel, 'Supports');
  assert.equal(v.sources[2].stanceLabel, 'Disputes');
});

test('locateQuote: highlights case-insensitively and rejects missing or tiny quotes', () => {
  const parts = locateQuote('Water boils at 100 degrees Celsius at sea level.', 'BOILS at 100 degrees', 10);
  assert.equal(parts.quote, 'boils at 100 degrees');
  assert.ok(parts.before.endsWith('Water '));
  assert.equal(locateQuote('some text here', 'not present anywhere'), null);
  assert.equal(locateQuote('boils', 'boils'), null);
  assert.equal(locateQuote('abc', null), null);
});

test('toClaimView: only decisive sources carry a highlighted quote', () => {
  const v = toClaimView(result({ evidence: [source({ stance: 'neutral', confidence: 0.5, quote: 'was still edible' })] }));
  assert.equal(v.sources[0].quoteParts, null);
});

test('toClaimView: calibrated flag follows calibration_status', () => {
  assert.equal(toClaimView(result()).calibrated, false);
  assert.equal(toClaimView(result({ signal: signal({ calibration_status: 'CALIBRATED_90_PCT' }) })).calibrated, true);
});

test('summarize: counts and wording', () => {
  const views = [
    toClaimView(result({ verdict: 'supported' })),
    toClaimView(result({ verdict: 'refuted' })),
    toClaimView(result({ verdict: 'mixed' })),
    toClaimView(result({ verdict: 'no_sources', evidence: [], sources_considered: 0, sources_relevant: 0 })),
  ];
  const s = summarize(views);
  assert.equal(s.title, '4 claims found');
  assert.equal(s.detail, '1 backed up, 1 disputed among sources, 1 refuted, 1 without sources');
  assert.equal(summarize(views.slice(0, 1)).title, '1 claim found');
});

test('truncate: collapses whitespace and adds an ellipsis', () => {
  assert.equal(truncate('a   b\n c', 20), 'a b c');
  assert.equal(truncate('abcdefghij', 5), 'abcd…');
});

test('normalizeBackendUrl: loopback http only', () => {
  assert.equal(normalizeBackendUrl('http://127.0.0.1:8000/'), 'http://127.0.0.1:8000');
  assert.equal(normalizeBackendUrl('http://localhost:9000/x'), 'http://localhost:9000');
  assert.equal(normalizeBackendUrl('https://example.com'), null);
  assert.equal(normalizeBackendUrl('not a url'), null);
});
