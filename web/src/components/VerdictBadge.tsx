import type { Headline, Verdict } from '../api/types'

/** Spec §6.4 — the one-to-one headline mapping, and what each state means. */
const HEADLINE_TEXT: Record<Headline, string> = {
  RED: 'RED — blocker',
  GRAY: 'GRAY — gaps block a verdict',
  AMBER: 'AMBER — caution',
  GREEN: 'GREEN — clear on the rules evaluated',
}

/**
 * Meaning never rides on colour alone (plan decision #10): every verdict
 * carries a glyph and a word as well as a hue, so the headline reads the same
 * to someone who cannot distinguish red from green.
 */
const HEADLINE_GLYPH: Record<Headline, string> = {
  RED: '✕', GRAY: '?', AMBER: '!', GREEN: '✓',
}

const VERDICT_TEXT: Record<Verdict, string> = {
  red: 'blocker',
  cannot_assess: 'cannot assess',
  amber: 'caution',
  pass: 'clear',
}

const VERDICT_GLYPH: Record<Verdict, string> = {
  red: '✕', cannot_assess: '?', amber: '!', pass: '✓',
}

export function HeadlineBadge({ headline }: { headline: Headline }) {
  return (
    <p className={`headline headline--${headline.toLowerCase()}`} data-testid="headline">
      <span className="headline__glyph" aria-hidden="true">{HEADLINE_GLYPH[headline]}</span>
      <span>{HEADLINE_TEXT[headline]}</span>
    </p>
  )
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`verdict verdict--${verdict}`}>
      <span aria-hidden="true">{VERDICT_GLYPH[verdict]}</span>
      {VERDICT_TEXT[verdict]}
    </span>
  )
}
