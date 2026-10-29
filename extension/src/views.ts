import { h } from './dom.js';
import { formatPct, type ClaimView, type MetricView, type SourceView } from './present.js';

/** Stateless rendering helpers. The controller (popup.ts) owns state and wiring. */

export function silentMeter(): HTMLElement {
  const wrap = h('div', { class: 'meter', 'aria-hidden': 'true' });
  for (let i = 0; i < 20; i += 1) wrap.append(h('span', { class: 'seg' }));
  return wrap;
}

export function meter(view: ClaimView): HTMLElement {
  const wrap = h('div', {
    class: 'meter',
    role: 'img',
    'aria-label': view.meterLabel,
    'data-verdict': view.verdict,
  });
  view.segments.forEach((tone, i) => {
    const seg = h('span', { class: tone === 'none' ? 'seg' : `seg ${tone}` });
    seg.style.setProperty('--i', String(i));
    wrap.append(seg);
  });
  return wrap;
}

function group(s: SourceView): 'supports' | 'refutes' | 'other' {
  return s.stance === 'supports' ? 'supports' : s.stance === 'refutes' ? 'refutes' : 'other';
}

export function sourceItem(s: SourceView): HTMLElement {
  const decisive = s.stance === 'supports' || s.stance === 'refutes';

  const chip = s.stanceLabel
    ? h(
        'span',
        { class: 'chip', 'data-stance': s.stance ?? '' },
        decisive && s.confidencePct !== null ? `${s.stanceLabel} ${s.confidencePct}%` : s.stanceLabel,
      )
    : null;
  const meta = h('span', { class: 'src-kind' }, s.year ? `${s.kindLabel}, ${s.year}` : s.kindLabel);

  const title = s.title
    ? s.url
      ? h('a', { class: 'src-title', href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.title)
      : h('span', { class: 'src-title' }, s.title)
    : null;

  const body = s.quoteParts
    ? h('p', { class: 'src-text' }, s.quoteParts.before, h('mark', {}, s.quoteParts.quote), s.quoteParts.after)
    : h('p', { class: 'src-text' }, s.snippet);

  const untitledLink =
    !s.title && s.url ? h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, 'Open source') : null;

  return h('li', { class: 'source', 'data-group': group(s) }, h('div', { class: 'src-head' }, chip, meta), title, body, untitledLink);
}

export function sourceFilters(list: HTMLElement, sources: SourceView[]): HTMLElement | null {
  const groups = new Set(sources.map(group));
  if (groups.size < 2 || sources.every((s) => s.stance === null)) return null;

  const options: [string, string][] = [['all', 'All']];
  if (groups.has('supports')) options.push(['supports', 'Supports']);
  if (groups.has('refutes')) options.push(['refutes', 'Disputes']);
  if (groups.has('other')) options.push(['other', 'Other']);

  const bar = h('div', { class: 'filters', role: 'group', 'aria-label': 'Filter sources' });
  for (const [value, label] of options) {
    const btn = h('button', { type: 'button', class: 'filter', 'aria-pressed': String(value === 'all') }, label);
    btn.addEventListener('click', () => {
      list.dataset.filter = value;
      bar.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
    });
    bar.append(btn);
  }
  return bar;
}

export function metricRow(m: MetricView): HTMLElement {
  const bar = h('span', { class: 'bar', 'data-tone': m.tone });
  const fill = h('span', { class: 'fill' });
  fill.style.width = `${Math.round((m.value ?? 0) * 100)}%`;
  bar.append(fill);
  return h(
    'div',
    { class: 'metric', title: m.hint },
    h('span', { class: 'm-label' }, m.label),
    bar,
    h('span', { class: 'm-value' }, formatPct(m.value)),
  );
}

export interface ClaimItemOptions {
  /** null: not highlighted on the page. true/false: whether this claim was found there. */
  onPage: boolean | null;
  onShow: () => void;
}

export function claimItem(view: ClaimView, opts: ClaimItemOptions): HTMLElement {
  const details = h('details', { class: 'more' }, h('summary', {}, 'Breakdown and sources'));

  details.append(h('div', { class: 'metrics' }, ...view.metrics.map(metricRow)));
  if (view.reason) {
    details.append(h('p', { class: 'reason' }, `Best guess (heuristic): ${view.reason}`));
  }

  if (view.sources.length > 0) {
    const list = h('ul', { class: 'sources' });
    list.dataset.filter = 'all';
    for (const s of view.sources) list.append(sourceItem(s));
    details.append(h('h3', {}, `Sources (${view.sources.length})`));
    const filters = sourceFilters(list, view.sources);
    if (filters) details.append(filters);
    details.append(list);
  } else {
    details.append(h('p', { class: 'reason' }, 'No sources were retrieved for this claim.'));
  }

  let pageNote: HTMLElement | null = null;
  if (opts.onPage === true) {
    pageNote = h('button', { type: 'button', class: 'link show-on-page' }, 'Show on page');
    pageNote.addEventListener('click', opts.onShow);
  } else if (opts.onPage === false) {
    pageNote = h('p', { class: 'basis' }, 'Not found on this page');
  }

  return h(
    'li',
    { class: 'claim', 'data-verdict': view.verdict },
    h('blockquote', {}, view.text),
    h(
      'div',
      { class: 'readout' },
      meter(view),
      h('p', { class: 'verdict' }, view.headline),
      view.basis ? h('p', { class: 'basis' }, view.basis) : null,
    ),
    view.explanation ? h('p', { class: 'why' }, view.explanation) : null,
    pageNote,
    details,
  );
}
