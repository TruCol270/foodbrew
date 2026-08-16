import type { Checkpoint, TrialBatch } from '../api/types'

const KIND_TITLES: Record<string, string> = {
  make_it: 'Making it',
  ph: 'pH',
  taste: 'Taste',
  usability: 'Using it',
  food_texture: 'What it did to the food',
  storage: 'Storage watch',
  symptom: 'Meals',
}

function when(minutes: number | null): string {
  if (minutes === null) return 'as it happens'
  if (minutes === 0) return 'straight away'
  if (minutes < 60) return `${minutes} min after making it`
  if (minutes < 60 * 24) return `${minutes / 60} hr after making it`
  return `day ${minutes / (60 * 24)}`
}

/** Spec §6.5 — generated from the evaluation's own gaps, never a blank form. */
export function ProtocolChecklist({ checkpoints, batch, notes }: {
  checkpoints: Checkpoint[]
  batch: TrialBatch | null
  notes: string[]
}) {
  const due = new Set(batch?.due_checkpoint_ids ?? [])
  const done = new Set(batch?.satisfied_checkpoint_ids ?? [])
  const scheduled = checkpoints.filter((c) => c.due_elapsed_minutes !== null)
  const perUse = checkpoints.filter((c) => c.due_elapsed_minutes === null)

  return (
    <section data-testid="protocol">
      <h3>What to watch</h3>
      <p className="blurb">
        Every item here comes from something this formulation could not settle on
        paper. Nothing was invented to fill a form.
      </p>

      <table>
        <thead><tr><th>When</th><th>What</th><th>Because of</th><th /></tr></thead>
        <tbody>
          {scheduled.map((c) => {
            const state = done.has(c.id) ? 'done' : due.has(c.id) ? 'due' : 'later'
            return (
              <tr key={c.id} data-testid={`checkpoint-${c.id}`} className={`checkpoint--${state}`}>
                <td>{when(c.due_elapsed_minutes)}</td>
                <td><strong>{KIND_TITLES[c.kind] ?? c.kind}</strong><br />{c.prompt}</td>
                <td>{c.raised_by.join(', ')}</td>
                <td data-testid={`checkpoint-state-${c.id}`}>
                  {state === 'done' ? 'recorded' : state === 'due' ? 'due now' : 'not yet'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <h4>Log these as they happen</h4>
      <ul data-testid="per-use-checkpoints">
        {perUse.map((c) => (
          <li key={c.id}>
            <strong>{KIND_TITLES[c.kind] ?? c.kind}</strong> — {c.prompt}{' '}
            <small className="blurb">({c.raised_by.join(', ')})</small>
          </li>
        ))}
      </ul>

      <h4>Before you start</h4>
      <ul data-testid="protocol-notes">
        {notes.map((note) => <li key={note}>{note}</li>)}
      </ul>
    </section>
  )
}
