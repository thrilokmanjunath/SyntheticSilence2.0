import type { ClaimResult } from './models/types.js';
import { headlineFor, type Verdict } from './present.js';

/** Plain-text exports of a finished check. Pure so they can be unit-tested. */

function oneLine(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function escapeMd(text: string): string {
  return oneLine(text).replace(/([\\`*_{}\[\]<>#|])/g, '\\$1');
}

const STANCE_WORD: Record<string, string> = {
  supports: 'Supports',
  refutes: 'Disputes',
  neutral: 'Related',
  irrelevant: 'Unrelated',
};

export interface ExportContext {
  checkedAt: Date;
  sourceText?: string;
}

export function toMarkdown(results: ClaimResult[], ctx: ExportContext): string {
  const lines: string[] = [];
  lines.push('# Evidence check');
  lines.push('');
  lines.push(`Checked ${ctx.checkedAt.toISOString().slice(0, 16).replace('T', ' ')} UTC with Synthetic Silence.`);
  lines.push('Automated check: a language model read retrieved sources, so a verdict can be wrong.');
  lines.push('');

  results.forEach((r, i) => {
    const verdict = (r.verdict ?? 'insufficient') as Verdict;
    lines.push(`## ${i + 1}. ${escapeMd(r.claim.original_text)}`);
    lines.push('');
    lines.push(`**${headlineFor(verdict, r.leaning)}**`);
    if (r.sources_considered) {
      lines.push(`(${r.sources_relevant ?? r.sources_considered} of ${r.sources_considered} sources relevant)`);
    }
    if (r.explanation?.trim()) {
      lines.push('');
      lines.push(oneLine(r.explanation));
    }
    const sources = r.evidence ?? [];
    if (sources.length > 0) {
      lines.push('');
      lines.push('Sources:');
      for (const s of sources) {
        const label = escapeMd(s.title || oneLine(s.text).slice(0, 80));
        const link = s.source_url ? `[${label}](${s.source_url})` : label;
        const stance = s.stance ? `${STANCE_WORD[s.stance] ?? s.stance}: ` : '';
        const year = s.publication_year ? ` (${s.publication_year})` : '';
        lines.push(`- ${stance}${link}${year}`);
        if (s.quote) lines.push(`  > ${escapeMd(s.quote)}`);
      }
    }
    lines.push('');
  });

  return lines.join('\n').trimEnd() + '\n';
}

export function toJson(results: ClaimResult[], ctx: ExportContext): string {
  return JSON.stringify(
    {
      checked_at: ctx.checkedAt.toISOString(),
      tool: 'Synthetic Silence',
      results,
    },
    null,
    2,
  );
}
