/**
 * Functions injected into the page with chrome.scripting.executeScript({ func }).
 *
 * Chrome serialises each function with toString(), so every function here must be completely
 * self-contained: no imports, no references to other module-level names. They are also exercised
 * directly in a real page by the e2e test.
 */

export interface HighlightItem {
  /** Strings to look for, in order of preference (the claim, then the sentence it came from). */
  needles: string[];
  kind: 'supported' | 'refuted' | 'mixed' | 'neutral';
}

export interface HighlightOutcome {
  found: boolean[];
}

export function applyHighlights(items: HighlightItem[]): HighlightOutcome {
  const STYLE_ID = 'ss-highlight-style';
  const KINDS = ['supported', 'refuted', 'mixed', 'neutral'] as const;
  const w = window as unknown as {
    __ssHighlights?: { ranges: (Range | null)[] };
  };
  const registry = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights;
  const HighlightCtor = (window as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight;
  if (!registry || !HighlightCtor) {
    return { found: items.map(() => false) };
  }

  // Start clean so repeated calls never stack highlights.
  for (const k of KINDS) registry.delete(`ss-${k}`);
  document.getElementById(STYLE_ID)?.remove();

  const fold = (ch: string): string => {
    switch (ch) {
      case '‘':
      case '’':
        return "'";
      case '“':
      case '”':
        return '"';
      case '–':
      case '—':
        return '-';
      default:
        return ch.toLowerCase();
    }
  };

  // Visible text nodes, skipping script-like containers and hidden subtrees.
  const skipTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'TEMPLATE', 'SVG', 'IFRAME']);
  const hidden = new Map<Element, boolean>();
  const isHidden = (el: Element | null): boolean => {
    if (!el) return false;
    const cached = hidden.get(el);
    if (cached !== undefined) return cached;
    const style = getComputedStyle(el);
    const result =
      style.display === 'none' || style.visibility === 'hidden' || skipTags.has(el.tagName.toUpperCase()) || isHidden(el.parentElement);
    hidden.set(el, result);
    return result;
  };

  const nodes: Text[] = [];
  const walker = document.createTreeWalker(document.body ?? document.documentElement, NodeFilter.SHOW_TEXT);
  let budget = 400_000;
  for (let n = walker.nextNode(); n && budget > 0; n = walker.nextNode()) {
    const text = n as Text;
    if (!text.data.trim() || isHidden(text.parentElement)) continue;
    nodes.push(text);
    budget -= text.data.length;
  }

  // One normalised string for the whole page, with a map back to (node, offset).
  let haystack = '';
  const mapNode: number[] = [];
  const mapOffset: number[] = [];
  let lastWasSpace = true;
  nodes.forEach((node, ni) => {
    for (let i = 0; i < node.data.length; i += 1) {
      const ch = node.data[i];
      let piece: string;
      if (/\s/.test(ch)) {
        if (lastWasSpace) continue;
        piece = ' ';
        lastWasSpace = true;
      } else {
        piece = fold(ch);
        lastWasSpace = false;
      }
      haystack += piece;
      // Case folding can change length (e.g. a capital I with a dot): keep one map entry per output unit.
      for (let k = 0; k < piece.length; k += 1) {
        mapNode.push(ni);
        mapOffset.push(i);
      }
    }
  });

  const normalise = (s: string): string => {
    let out = '';
    let space = true;
    for (const ch of s) {
      if (/\s/.test(ch)) {
        if (!space) out += ' ';
        space = true;
      } else {
        out += fold(ch);
        space = false;
      }
    }
    return out.trim();
  };

  const ranges: (Range | null)[] = [];
  const grouped: Record<string, Range[]> = { supported: [], refuted: [], mixed: [], neutral: [] };

  for (const item of items) {
    let range: Range | null = null;
    for (const needle of item.needles) {
      const q = normalise(needle).replace(/[.!?]+$/, '');
      if (q.length < 8) continue;
      const at = haystack.indexOf(q);
      if (at === -1) continue;
      const last = at + q.length - 1;
      const r = document.createRange();
      r.setStart(nodes[mapNode[at]], mapOffset[at]);
      r.setEnd(nodes[mapNode[last]], mapOffset[last] + 1);
      range = r;
      break;
    }
    ranges.push(range);
    if (range) grouped[item.kind].push(range);
  }

  for (const k of KINDS) {
    if (grouped[k].length > 0) registry.set(`ss-${k}`, new HighlightCtor(...grouped[k]));
  }

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = [
    '::highlight(ss-supported){background-color:rgba(14,138,140,.30);color:inherit}',
    '::highlight(ss-refuted){background-color:rgba(192,58,91,.28);color:inherit}',
    '::highlight(ss-mixed){background-color:rgba(120,130,150,.30);color:inherit;text-decoration:underline wavy rgba(192,58,91,.9)}',
    '::highlight(ss-neutral){background-color:rgba(120,130,150,.26);color:inherit;text-decoration:underline rgba(78,93,108,.9)}',
  ].join('\n');
  (document.head ?? document.documentElement).appendChild(style);

  w.__ssHighlights = { ranges };
  return { found: ranges.map((r) => r !== null) };
}

export function clearHighlights(): boolean {
  const w = window as unknown as { __ssHighlights?: unknown };
  const registry = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights;
  let had = false;
  if (registry) {
    for (const k of ['supported', 'refuted', 'mixed', 'neutral']) {
      if (registry.delete(`ss-${k}`)) had = true;
    }
  }
  document.getElementById('ss-highlight-style')?.remove();
  delete w.__ssHighlights;
  return had;
}

export function scrollToHighlight(index: number): boolean {
  const w = window as unknown as { __ssHighlights?: { ranges: (Range | null)[] } };
  const range = w.__ssHighlights?.ranges[index];
  if (!range) return false;
  const rect = range.getBoundingClientRect();
  const top = rect.top + window.scrollY - window.innerHeight / 2;
  window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  return true;
}

export function readPageSelection(): string {
  return window.getSelection()?.toString() ?? '';
}
