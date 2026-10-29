import type { ClaimResult } from './models/types.js';

/**
 * State machine for the NDJSON analysis stream (POST /api/v1/analyze/stream).
 * Pure functions so the incremental behaviour can be unit-tested without a browser.
 */

export interface StreamError {
  kind: string;
  message: string;
}

export interface ClaimStub {
  id: string;
  original_text: string;
  context: string;
}

export type StreamEvent =
  | { type: 'claims'; claims: ClaimStub[]; truncated: boolean }
  | { type: 'claim'; index: number; result: ClaimResult }
  | { type: 'claim_error'; index: number; error: StreamError }
  | { type: 'error'; error: StreamError }
  | { type: 'done' };

export type Slot =
  | { status: 'pending'; id: string; text: string }
  | { status: 'done'; id: string; text: string; result: ClaimResult }
  | { status: 'error'; id: string; text: string; error: StreamError };

export interface StreamState {
  slots: Slot[];
  truncated: boolean;
  /** The server sent its final "done" line. */
  done: boolean;
  /** Nothing could be analysed. */
  fatal: StreamError | null;
}

export function initialState(): StreamState {
  return { slots: [], truncated: false, done: false, fatal: null };
}

export function reduce(state: StreamState, event: StreamEvent): StreamState {
  switch (event.type) {
    case 'claims':
      return {
        ...state,
        truncated: event.truncated === true,
        slots: event.claims.map((c) => ({ status: 'pending', id: c.id, text: c.original_text })),
      };
    case 'claim': {
      const current = state.slots[event.index];
      if (!current) return state; // result for a claim we were never told about: ignore
      const slots = state.slots.slice();
      slots[event.index] = { status: 'done', id: current.id, text: current.text, result: event.result };
      return { ...state, slots };
    }
    case 'claim_error': {
      const current = state.slots[event.index];
      if (!current) return state;
      const slots = state.slots.slice();
      slots[event.index] = { status: 'error', id: current.id, text: current.text, error: event.error };
      return { ...state, slots };
    }
    case 'error':
      return { ...state, fatal: event.error };
    case 'done':
      return { ...state, done: true };
    default:
      return state;
  }
}

/** Puts a finished or failed slot back to pending so it can be re-checked. */
export function retrySlot(state: StreamState, index: number): StreamState {
  const current = state.slots[index];
  if (!current) return state;
  const slots = state.slots.slice();
  slots[index] = { status: 'pending', id: current.id, text: current.text };
  return { ...state, slots };
}

export function progress(state: StreamState): { finished: number; total: number } {
  return {
    finished: state.slots.filter((s) => s.status !== 'pending').length,
    total: state.slots.length,
  };
}

/** True once the stream reached a terminal line, so a dropped connection can be told apart. */
export function isTerminal(state: StreamState): boolean {
  return state.done || state.fatal !== null;
}

/**
 * Splits an incoming text buffer into complete NDJSON events and the unfinished tail.
 * Lines that are not valid JSON objects with a string `type` are skipped, not fatal.
 */
export function parseLines(buffer: string): { events: StreamEvent[]; rest: string } {
  const parts = buffer.split('\n');
  const rest = parts.pop() ?? '';
  const events: StreamEvent[] = [];
  for (const raw of parts) {
    const line = raw.trim();
    if (!line) continue;
    try {
      const parsed: unknown = JSON.parse(line);
      if (parsed && typeof parsed === 'object' && typeof (parsed as { type?: unknown }).type === 'string') {
        events.push(parsed as StreamEvent);
      }
    } catch {
      /* ignore a malformed line */
    }
  }
  return { events, rest };
}
