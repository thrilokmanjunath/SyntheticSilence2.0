import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialState, isTerminal, parseLines, progress, reduce } from '../dist/stream.js';

const stub = (id, text) => ({ id, original_text: text, context: text });
const result = (id) => ({ claim: { id, original_text: id, context: '' }, signal: {}, explanation: '', evidence: [], verdict: 'supported' });

test('claims event creates one pending slot per claim', () => {
  const s = reduce(initialState(), { type: 'claims', claims: [stub('c1', 'A'), stub('c2', 'B')], truncated: true });
  assert.deepEqual(s.slots.map((x) => [x.status, x.text]), [['pending', 'A'], ['pending', 'B']]);
  assert.equal(s.truncated, true);
  assert.deepEqual(progress(s), { finished: 0, total: 2 });
});

test('results arrive out of order and fill their own slot', () => {
  let s = reduce(initialState(), { type: 'claims', claims: [stub('c1', 'A'), stub('c2', 'B'), stub('c3', 'C')], truncated: false });
  s = reduce(s, { type: 'claim', index: 2, result: result('c3') });
  assert.deepEqual(s.slots.map((x) => x.status), ['pending', 'pending', 'done']);
  s = reduce(s, { type: 'claim_error', index: 0, error: { kind: 'retrieval', message: 'down' } });
  assert.deepEqual(s.slots.map((x) => x.status), ['error', 'pending', 'done']);
  assert.deepEqual(progress(s), { finished: 2, total: 3 });
  assert.equal(s.slots[0].error.message, 'down');
});

test('reduce does not mutate the previous state', () => {
  const a = reduce(initialState(), { type: 'claims', claims: [stub('c1', 'A')], truncated: false });
  const b = reduce(a, { type: 'claim', index: 0, result: result('c1') });
  assert.equal(a.slots[0].status, 'pending');
  assert.equal(b.slots[0].status, 'done');
});

test('events for unknown indices are ignored', () => {
  const a = reduce(initialState(), { type: 'claims', claims: [stub('c1', 'A')], truncated: false });
  assert.equal(reduce(a, { type: 'claim', index: 5, result: result('x') }), a);
  assert.equal(reduce(a, { type: 'claim_error', index: -1, error: { kind: 'x', message: 'y' } }), a);
});

test('terminal detection: done or fatal error, nothing else', () => {
  const s = reduce(initialState(), { type: 'claims', claims: [stub('c1', 'A')], truncated: false });
  assert.equal(isTerminal(s), false);
  assert.equal(isTerminal(reduce(s, { type: 'done' })), true);
  const fatal = reduce(s, { type: 'error', error: { kind: 'llm', message: 'no credit' } });
  assert.equal(isTerminal(fatal), true);
  assert.equal(fatal.fatal.message, 'no credit');
});

test('parseLines: complete lines become events, the partial tail is kept', () => {
  const first = parseLines('{"type":"claims","claims":[],"truncated":false}\n{"type":"cla');
  assert.equal(first.events.length, 1);
  assert.equal(first.events[0].type, 'claims');
  assert.equal(first.rest, '{"type":"cla');

  const second = parseLines(first.rest + 'im","index":0}\n{"type":"done"}\n');
  assert.deepEqual(second.events.map((e) => e.type), ['claim', 'done']);
  assert.equal(second.rest, '');
});

test('parseLines: skips blank, malformed and untyped lines', () => {
  const { events } = parseLines('\n not json \n{"nope":1}\n[1,2]\n{"type":"done"}\n');
  assert.deepEqual(events.map((e) => e.type), ['done']);
});
