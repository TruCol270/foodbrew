import type { Tracked, TruthLabel } from '../api/types'

/** Spec §5.4 — the closed enum. Anything else is a bug, and shows as one. */
const LABEL_TEXT: Record<TruthLabel, string> = {
  confirmed: 'confirmed',
  unconfirmed: 'not confirmed',
  user_provided: 'you entered this',
  calculated: 'calculated',
  observed: 'observed in a trial',
}

export function TruthValue({
  tracked, unit = '', missingText = 'not confirmed',
}: {
  tracked: Tracked
  unit?: string
  missingText?: string
}) {
  const hasValue = tracked.value !== null && tracked.value !== undefined
  const shown =
    typeof tracked.value === 'boolean'
      ? tracked.value ? 'yes' : 'no'
      : hasValue ? String(tracked.value) : missingText

  return (
    <span className={`truth truth--${tracked.status}`} title={tracked.source || undefined}>
      {shown}{hasValue && unit ? ` ${unit}` : ''}
      <small className="truth__label"> ({LABEL_TEXT[tracked.status]})</small>
    </span>
  )
}
