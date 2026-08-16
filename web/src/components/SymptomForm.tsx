import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Food, SymptomDose } from '../api/types'

function doseLine(entry: SymptomDose['enzymes'][number]): string {
  if (entry.units_delivered === null || entry.threshold.value === null) {
    return `${entry.enzyme_name}: cannot work the dose out yet — ${
      entry.blocking_field || 'something is missing'
    }.`
  }
  const verdict = entry.meets_threshold ? 'clears the evidence threshold' : 'is below it'
  return `${entry.enzyme_name}: ${entry.units_delivered} ${entry.dose_unit} delivered against ` +
    `${entry.threshold.value} ${entry.dose_unit} — ${verdict}.`
}

/** Spec §5.3 — the only route for symptom capture, so the dose is always attached. */
export function SymptomForm({ batchId, triggerFoods, onSubmit }: {
  batchId: string
  triggerFoods: Food[]
  onSubmit: (body: unknown) => Promise<void>
}) {
  const [foodId, setFoodId] = useState(triggerFoods[0]?.id ?? '')
  const [amount, setAmount] = useState('1')
  const [doses, setDoses] = useState('1')
  const [outcome, setOutcome] = useState('3')
  const [notes, setNotes] = useState('')
  const [preview, setPreview] = useState<SymptomDose | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!foodId) return
    const handle = setTimeout(() => {
      api
        .previewSymptom(batchId, {
          trigger_food_id: foodId,
          amount_value: amount === '' ? null : Number(amount),
          amount_unit: 'servings',
          doses_used: doses === '' ? null : Number(doses),
        })
        .then(setPreview)
        .catch(() => setPreview(null))
    }, 300)
    return () => clearTimeout(handle)
  }, [batchId, foodId, amount, doses])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await onSubmit({
        trigger_food_id: foodId,
        amount_value: amount === '' ? null : Number(amount),
        amount_unit: 'servings',
        doses_used: doses === '' ? null : Number(doses),
        outcome_score: Number(outcome),
        notes,
      })
      setNotes('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="symptom-form">
      <h3>Log a meal</h3>
      <label>What did you eat?
        <select data-testid="symptom-food" value={foodId}
                onChange={(e) => setFoodId(e.target.value)}>
          {triggerFoods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
      </label>
      <label>How many servings?
        <input data-testid="symptom-amount" value={amount}
               onChange={(e) => setAmount(e.target.value)} />
      </label>
      <label>How many doses of the dressing?
        <input data-testid="symptom-doses" value={doses}
               onChange={(e) => setDoses(e.target.value)} />
      </label>

      <div data-testid="dose-preview" className="blurb">
        {preview === null ? (
          'Working out the dose…'
        ) : (
          <>
            <ul>
              {preview.enzymes.map((entry) => (
                <li key={entry.enzyme_id}>{doseLine(entry)}</li>
              ))}
            </ul>
            {preview.note && <p>{preview.note}</p>}
          </>
        )}
      </div>

      <label>How did it go? (1 fine — 5 bad)
        <select data-testid="symptom-outcome" value={outcome}
                onChange={(e) => setOutcome(e.target.value)}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <label>Notes
        <textarea data-testid="symptom-notes" value={notes}
                  onChange={(e) => setNotes(e.target.value)} />
      </label>
      <p className="blurb">
        One person, not blinded, on a product you have a stake in. The report carries
        these as questions for a food scientist, with this dose arithmetic attached —
        so a result that means nothing can be told apart from one that does.
      </p>
      <button type="submit" data-testid="save-symptom" disabled={busy}>
        {busy ? 'Saving…' : 'Save this meal'}
      </button>
    </form>
  )
}
