import type { SnapshotChange } from '../api/types'

const KIND_TEXT: Record<string, string> = {
  enzyme: 'enzyme',
  food: 'food',
  substrate: 'substrate',
  formulation: 'formulation',
  gi_regions: 'digestive-tract model',
  latest_trial_ph: 'trial pH reading',
  field_added: 'field added by a catalogue upgrade',
}

/**
 * Spec §10 screen 4 — "data changed since this evaluation — re-run to refresh".
 *
 * Decision #3 / Task 9: a `field_added` change means a column was added by a
 * migration, not that the founder edited a record. When every change this
 * evaluation carries is that kind, the banner says so rather than implying an
 * edit happened.
 */
export function StaleBanner({ changes, onRerun }: {
  changes: SnapshotChange[]
  onRerun: () => void
}) {
  const isUpgradeOnly = changes.length > 0 && changes.every((c) => c.kind === 'field_added')
  return (
    <aside className="banner banner--stale" data-testid="stale-banner">
      <p>
        {isUpgradeOnly ? (
          <>
            this evaluation predates a catalogue upgrade — re-run to pick up the
            new fields
          </>
        ) : (
          <>
            A record this run used has changed since it ran. What you see below is
            the record of that run and does not update on its own — re-run to see
            the effect.
          </>
        )}
      </p>
      {changes.length > 0 && (
        <ul>
          {changes.slice(0, 8).map((change, index) => (
            <li key={`${change.record_id}-${change.field}-${index}`}>
              {KIND_TEXT[change.kind] ?? change.kind} <code>{change.record_id}</code>
              {change.field !== '*' && <> — <code>{change.field}</code></>}
            </li>
          ))}
          {changes.length > 8 && <li>…and {changes.length - 8} more</li>}
        </ul>
      )}
      <button type="button" onClick={onRerun} data-testid="rerun">Re-run the checks</button>
    </aside>
  )
}
