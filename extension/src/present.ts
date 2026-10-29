import type { ClaimResult, Evidence } from './models/types.js';

/**
 * Pure presentation logic: turns backend results into what the popup shows.
 * No DOM access here so it can be unit-tested with `node --test`.
 *
 * The verdict comes from the backend and is derived from what the sources say about the claim.
 * It is never derived from the density-based gap score: the research finding for this project is
 * that the density signal does not generalise across constructions, so it is shown only as an
 * experimental number in research mode.
 */

export const SEGMENTS = 20;

export type Verdict = 'supported' | 'refuted' | 'mixed' | 'insufficient' | 'no_sources';
export type Stance = 'supports' | 'refutes' | 'neutral' | 'irrelevant';
export type Tone = 'support' | 'conflict' | 'none';

export interface MetricView {
  key: string;
  label: string;
  hint: string;
  value: number | null; // 0..1, null when unavailable
  tone: 'support' | 'conflict' | 'neutral';
}

export interface QuoteParts {
  before: string;
  quote: string;
  after: string;
}

export interface SourceView {
  id: string;
  title: string | null;
  kindLabel: string;
  stance: Stance | null;
  stanceLabel: string | null;
  confidencePct: number | null;
  snippet: string;
  quoteParts: QuoteParts | null;
  url: string | null;
  year: number | null;
}

export interface ClaimView {
  id: string;
  text: string;
  verdict: Verdict;
  headline: string;
  segments: Tone[];
  meterLabel: string;
  supportPct: number;
  conflictPct: number;
  basis: string | null;
  explanation: string;
  reason: string | null;
  calibrated: boolean;
  metrics: MetricView[];
  sources: SourceView[];
}

export interface ViewOptions {
  /** Show the experimental density/entropy signals. Off by default. */
  research?: boolean;
}

const REASONS: Record<string, string> = {
  missing_evidence: 'No relevant sources turned up for this claim.',
  contradictory: 'Retrieved sources lean against the claim.',
  temporal_novelty: 'Most sources are very recent, so the record may still be forming.',
  ambiguous_claim: 'Sources are related but don’t clearly confirm or refute the claim.',
  retrieved_insufficient: 'Sources were found but cover only part of the claim.',
  wrong_retrieval: 'Retrieved sources may be about something else.',
  rare_valid: 'The claim looks unusual compared with typical supported claims.',
  long_tail: 'The topic is niche, so there is little to compare against.',
  ood: 'The claim sits far from the material the system was tuned on.',
  hallucination: 'The claim may not be grounded in anything checkable.',
};

const STANCE_LABELS: Record<Stance, string> = {
  supports: 'Supports',
  refutes: 'Disputes',
  neutral: 'Related',
  irrelevant: 'Unrelated',
};

const STANCE_ORDER: Record<Stance, number> = { supports: 0, refutes: 1, neutral: 2, irrelevant: 3 };

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function clamp01(v: number | null): number {
  if (v === null) return 0;
  return Math.min(1, Math.max(0, v));
}

export function headlineFor(verdict: Verdict, leaning: string | null | undefined): string {
  switch (verdict) {
    case 'supported':
      return 'Sources back this up';
    case 'refuted':
      return 'Sources push against this';
    case 'mixed':
      return 'Sources disagree';
    case 'no_sources':
      return 'No sources found';
    default:
      if (leaning === 'supports') return 'Leans true, not settled';
      if (leaning === 'refutes') return 'Leans false, not settled';
      return 'Sources don’t settle it';
  }
}

/** Builds the 20 meter segments. Support fills from the left, conflict from the right when both exist. */
export function buildSegments(verdict: Verdict, support: number, conflict: number): Tone[] {
  const out: Tone[] = new Array(SEGMENTS).fill('none');
  if (verdict === 'no_sources') return out;

  const s = Math.round(clamp01(support) * SEGMENTS);
  const c = Math.round(clamp01(conflict) * SEGMENTS);

  if (verdict === 'refuted' || (verdict === 'insufficient' && c > s)) {
    for (let i = 0; i < c; i += 1) out[i] = 'conflict';
    return out;
  }
  for (let i = 0; i < s; i += 1) out[i] = 'support';
  if (verdict === 'mixed') {
    // Never let the two sides overwrite each other.
    const room = SEGMENTS - s;
    for (let i = 0; i < Math.min(c, room); i += 1) out[SEGMENTS - 1 - i] = 'conflict';
  }
  return out;
}

export function truncate(text: string, max: number): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  if (flat.length <= max) return flat;
  return flat.slice(0, max - 1).trimEnd() + '…';
}

function safeUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.toString() : null;
  } catch {
    return null;
  }
}

/** Splits `text` around `quote` (case and whitespace insensitive) so the UI can highlight it. */
export function locateQuote(text: string, quote: string | null | undefined, context = 90): QuoteParts | null {
  if (!quote) return null;
  const flatText = text.replace(/\s+/g, ' ');
  const flatQuote = quote.replace(/\s+/g, ' ').trim();
  if (flatQuote.length < 8) return null;
  const at = flatText.toLowerCase().indexOf(flatQuote.toLowerCase());
  if (at === -1) return null;

  const start = Math.max(0, at - context);
  const end = Math.min(flatText.length, at + flatQuote.length + context);
  return {
    before: (start > 0 ? '…' : '') + flatText.slice(start, at),
    quote: flatText.slice(at, at + flatQuote.length),
    after: flatText.slice(at + flatQuote.length, end) + (end < flatText.length ? '…' : ''),
  };
}

function sourceView(e: Evidence): SourceView {
  const stance = (e.stance ?? null) as Stance | null;
  const quoteParts = stance === 'supports' || stance === 'refutes' ? locateQuote(e.text, e.quote) : null;
  return {
    id: e.id,
    title: e.title ?? null,
    kindLabel: e.kind === 'encyclopedia' ? 'Wikipedia' : 'Scholarly',
    stance,
    stanceLabel: stance ? STANCE_LABELS[stance] : null,
    confidencePct: num(e.confidence) === null ? null : Math.round(clamp01(num(e.confidence)) * 100),
    snippet: truncate(e.text, 220),
    quoteParts,
    url: safeUrl(e.source_url),
    year: num(e.publication_year),
  };
}

function sortSources(sources: SourceView[]): SourceView[] {
  // Decisive sources first (higher confidence first), then related, then unrelated. Stable otherwise.
  return sources
    .map((s, i) => ({ s, i }))
    .sort((a, b) => {
      const oa = a.s.stance ? STANCE_ORDER[a.s.stance] : 2;
      const ob = b.s.stance ? STANCE_ORDER[b.s.stance] : 2;
      if (oa !== ob) return oa - ob;
      const ca = a.s.confidencePct ?? 0;
      const cb = b.s.confidencePct ?? 0;
      return cb - ca || a.i - b.i;
    })
    .map((x) => x.s);
}

export function toClaimView(result: ClaimResult, options: ViewOptions = {}): ClaimView {
  const s = result.signal;
  const evidence = result.evidence ?? [];
  const verdict = (result.verdict ?? (evidence.length === 0 ? 'no_sources' : 'insufficient')) as Verdict;
  const support = clamp01(num(s.semantic_support));
  const conflict = clamp01(num(s.contradiction_level));

  const metrics: MetricView[] = [
    {
      key: 'support',
      label: 'Support',
      hint: 'Confidence-weighted share of relevant sources that back the claim.',
      value: num(s.semantic_support),
      tone: 'support',
    },
    {
      key: 'conflict',
      label: 'Conflict',
      hint: 'Confidence-weighted share of relevant sources that dispute the claim.',
      value: num(s.contradiction_level),
      tone: 'conflict',
    },
    {
      key: 'recent',
      label: 'Recent sources',
      hint: 'Share of sources published after the cutoff year. Wikipedia pages have no date.',
      value: num(s.temporal_coverage),
      tone: 'neutral',
    },
  ];
  if (options.research) {
    metrics.push(
      {
        key: 'density',
        label: 'Density distance',
        hint: 'kNN cosine distance from the FEVER reference manifold. Research signal.',
        value: num(s.representation_density),
        tone: 'neutral',
      },
      {
        key: 'uncertainty',
        label: 'Spread',
        hint: 'Entropy of claim-source similarity. High means no source stands out.',
        value: num(s.uncertainty),
        tone: 'neutral',
      },
      {
        key: 'gap',
        label: 'Gap score (experimental)',
        hint: 'Uncalibrated research composite (density and entropy). It often disagrees with support, so read the verdict above instead.',
        value: num(s.insufficiency_signal),
        tone: 'neutral',
      },
    );
  }

  const considered = result.sources_considered ?? evidence.length;
  const relevant = result.sources_relevant ?? considered;
  const family = s.construction_family_estimate;

  return {
    id: result.claim.id,
    text: result.claim.original_text,
    verdict,
    headline: headlineFor(verdict, result.leaning),
    segments: buildSegments(verdict, support, conflict),
    meterLabel:
      verdict === 'refuted'
        ? `Source conflict ${Math.round(conflict * 100)} percent`
        : verdict === 'mixed'
          ? `Sources split: support ${Math.round(support * 100)} percent, conflict ${Math.round(conflict * 100)} percent`
          : `Source support ${Math.round(support * 100)} percent`,
    supportPct: Math.round(support * 100),
    conflictPct: Math.round(conflict * 100),
    basis: considered > 0 ? `${relevant} of ${considered} ${considered === 1 ? 'source is' : 'sources are'} relevant` : null,
    explanation: (result.explanation ?? '').trim(),
    reason: options.research && family ? REASONS[family] ?? null : null,
    calibrated: s.calibration_status !== 'NOT_CALIBRATED',
    metrics,
    sources: sortSources(evidence.map(sourceView)),
  };
}

export interface Summary {
  total: number;
  counts: Record<Verdict, number>;
  title: string;
  detail: string;
  anyUncalibrated: boolean;
}

export function summarize(views: ClaimView[]): Summary {
  const counts: Record<Verdict, number> = { supported: 0, refuted: 0, mixed: 0, insufficient: 0, no_sources: 0 };
  for (const v of views) counts[v.verdict] += 1;
  const total = views.length;

  const title = total === 1 ? '1 claim found' : `${total} claims found`;
  const parts: string[] = [];
  if (counts.supported) parts.push(`${counts.supported} backed up`);
  if (counts.insufficient) parts.push(`${counts.insufficient} unsettled`);
  if (counts.mixed) parts.push(`${counts.mixed} disputed among sources`);
  if (counts.refuted) parts.push(`${counts.refuted} refuted`);
  if (counts.no_sources) parts.push(`${counts.no_sources} without sources`);

  return {
    total,
    counts,
    title,
    detail: parts.join(', '),
    anyUncalibrated: views.some((v) => !v.calibrated),
  };
}

export function formatPct(value: number | null): string {
  return value === null ? 'n/a' : `${Math.round(clamp01(value) * 100)}%`;
}
