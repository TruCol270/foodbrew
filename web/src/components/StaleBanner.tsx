import type { SnapshotChange } from '../api/types'

const KIND_TEXT: Record<string, string> = {
  enzyme: 'enzyme',
  food: 'food',
  substrate: 'substrate',
  formulation: 'formulation',
  gi_regions: 'digestive-tract model',
  latest_trial_ph: 'trial pH reading',
}

/** Spec §10 screen 4 — "data changed since this evaluation — re-run to refresh". */
export function StaleBanner({ changes, onRerun }: {
  changes: SnapshotChange[]
  onRerun: () => void
}) {
  return (
    <aside className="banner banner--stale" data-testid="stale-banner">
      <p>
        A record this run used has changed since it ran. What you see below is the
        record of that run and does not update on its own — re-run to see the effect.
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
