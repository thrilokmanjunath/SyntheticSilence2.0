import type { Verdict } from './present.js';

export interface Badge {
  text: string;
  color: string;
}

const COLORS = {
  refuted: '#C03A5B',
  supported: '#0E8A8C',
  other: '#4E5D6C',
  working: '#4E5D6C',
  failed: '#C03A5B',
} as const;

/** Toolbar badge for a finished check: claim count, coloured by the most serious verdict. */
export function badgeFor(verdicts: Verdict[]): Badge {
  if (verdicts.length === 0) return { text: '', color: COLORS.other };
  const text = verdicts.length > 99 ? '99+' : String(verdicts.length);
  if (verdicts.includes('refuted')) return { text, color: COLORS.refuted };
  if (verdicts.every((v) => v === 'supported')) return { text, color: COLORS.supported };
  return { text, color: COLORS.other };
}

export const WORKING: Badge = { text: '…', color: COLORS.working };
export const FAILED: Badge = { text: '!', color: COLORS.failed };
export const CLEARED: Badge = { text: '', color: COLORS.other };

/** Sets the badge for one tab. Never throws: a badge is cosmetic. */
export async function setBadge(badge: Badge, tabId?: number): Promise<void> {
  try {
    const scope = tabId === undefined ? {} : { tabId };
    await chrome.action.setBadgeText({ text: badge.text, ...scope });
    if (badge.text) await chrome.action.setBadgeBackgroundColor({ color: badge.color, ...scope });
  } catch {
    /* tab closed or API unavailable */
  }
}
