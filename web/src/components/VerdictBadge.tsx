import type { Headline, Verdict } from '../api/types'

/** Spec §6.4 — the one-to-one headline mapping, and what each state means. */
const HEADLINE_TEXT: Record<Headline, string> = {
  RED: 'RED — blocker',
  GRAY: 'GRAY — gaps block a verdict',
  AMBER: 'AMBER — caution',
  GREEN: 'GREEN — clear on the rules evaluated',
}

const VERDICT_TEXT: Record<Verdict, string> = {
  red: 'blocker',
  cannot_assess: 'cannot assess',
  amber: 'caution',
  pass: 'clear',
}

export function HeadlineBadge({ headline }: { headline: Headline }) {
  return (
    <p className={`headline headline--${headline.toLowerCase()}`} data-testid="headline">
      {HEADLINE_TEXT[headline]}
    </p>
  )
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={`verdict verdict--${verdict}`}>{VERDICT_TEXT[verdict]}</span>
}
