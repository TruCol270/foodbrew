import { useState } from 'react'

const AMBIENT_LIMIT = 4.6

/**
 * Spec §3 Workflow E and §10 screen 6 — the ambient control stays disabled until
 * a measured pH below 4.6 is in the form. The API refuses it too (plan decision
 * #5); this is the half that stops her filling a form she cannot submit.
 */
export function BatchForm({ onSubmit }: { onSubmit: (body: unknown) => Promise<void> }) {
  const [ph, setPh] = useState('')
  const [phMethod, setPhMethod] = useState<'none' | 'strip' | 'meter'>('none')
  const [ambient, setAmbient] = useState(false)
  const [sizeG, setSizeG] = useState('')
  const [minutes, setMinutes] = useState('')
  const [difficulty, setDifficulty] = useState('3')
  const [step, setStep] = useState('')
  const [sourceNote, setSourceNote] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)

  const phValue = ph === '' ? null : Number(ph)
  const ambientAllowed = phValue !== null && phValue < AMBIENT_LIMIT && phMethod !== 'none'
  const storageMode = ambient && ambientAllowed ? 'ambient' : 'refrigerated'

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await onSubmit({
        batch_size_g: sizeG === '' ? null : Number(sizeG),
        measured_ph: phValue,
        ph_method: phMethod,
        make_minutes: minutes === '' ? null : Number(minutes),
        difficulty_score: Number(difficulty),
        enzyme_source_note: sourceNote,
        enzyme_addition_step: step === '' ? null : Number(step),
        process_notes: notes,
        storage_mode: storageMode,
      })
      setPh(''); setPhMethod('none'); setAmbient(false); setSizeG('')
      setMinutes(''); setStep(''); setSourceNote(''); setNotes('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="batch-form">
      <h3>Log a batch</h3>
      <label>How much did you make? (g)
        <input data-testid="batch-size" value={sizeG} onChange={(e) => setSizeG(e.target.value)} />
      </label>
      <label>How many minutes did it take?
        <input data-testid="batch-minutes" value={minutes}
               onChange={(e) => setMinutes(e.target.value)} />
      </label>
      <label>How hard was it? (1 easy — 5 hard)
        <select data-testid="batch-difficulty" value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <label>Which step did the enzyme go in after?
        <input data-testid="batch-step" value={step} onChange={(e) => setStep(e.target.value)} />
      </label>
      <label>Where did the enzyme come from?
        <input data-testid="batch-source" value={sourceNote}
               placeholder="e.g. two Lactaid Fast Act capsules opened"
               onChange={(e) => setSourceNote(e.target.value)} />
      </label>

      <fieldset>
        <legend>pH (optional)</legend>
        <label>Reading
          <input data-testid="batch-ph" value={ph} onChange={(e) => setPh(e.target.value)} />
        </label>
        <label>Measured with
          <select data-testid="batch-ph-method" value={phMethod}
                  onChange={(e) => setPhMethod(e.target.value as typeof phMethod)}>
            <option value="none">not measured</option>
            <option value="strip">a strip</option>
            <option value="meter">a meter</option>
          </select>
        </label>
      </fieldset>

      <label>
        <input type="checkbox" data-testid="batch-ambient" checked={ambient && ambientAllowed}
               disabled={!ambientAllowed} onChange={(e) => setAmbient(e.target.checked)} />
        Watch a jar at room temperature
      </label>
      {!ambientAllowed && (
        <p className="blurb" data-testid="ambient-gate">
          Room-temperature watching needs a measured pH below {AMBIENT_LIMIT} for this
          batch. Without that reading the schedule stays refrigerated.
        </p>
      )}

      <label>Anything go wrong?
        <textarea data-testid="batch-notes" value={notes}
                  onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button type="submit" data-testid="save-batch" disabled={busy}>
        {busy ? 'Saving…' : 'Save this batch'}
      </button>
    </form>
  )
}
