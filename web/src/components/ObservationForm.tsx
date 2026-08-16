import { useState } from 'react'

import type { Food, ObservationType } from '../api/types'

const TYPES: { value: ObservationType; label: string }[] = [
  { value: 'taste', label: 'Taste and smell' },
  { value: 'usability', label: 'Using it' },
  { value: 'food_texture', label: 'What it did to the food' },
  { value: 'storage', label: 'The jar in storage' },
]

/** Spec §6.6 — the two rigor flags are per observation, ticked when they apply. */
const SCALE = [
  '1 — indistinguishable from the undressed portion',
  '2 — slightly softer, would not notice without comparing',
  '3 — clearly softer than the undressed portion',
  '4 — limp, wilted, or watery',
  '5 — badly broken down',
]

export function ObservationForm({ applicationFoods, onSubmit }: {
  applicationFoods: Food[]
  onSubmit: (body: unknown) => Promise<void>
}) {
  const [type, setType] = useState<ObservationType>('taste')
  const [minutes, setMinutes] = useState('0')
  const [score, setScore] = useState('3')
  const [foodId, setFoodId] = useState(applicationFoods[0]?.id ?? '')
  const [text, setText] = useState('')
  const [blinded, setBlinded] = useState(false)
  const [control, setControl] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await onSubmit({
        type,
        elapsed_minutes: Number(minutes),
        score: Number(score),
        free_text: text,
        was_blinded: blinded,
        had_undressed_control: control,
        application_food_id: type === 'food_texture' ? foodId : '',
      })
      setText(''); setBlinded(false); setControl(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="observation-form">
      <h3>Record what you saw</h3>
      <label>What are you recording?
        <select data-testid="observation-type" value={type}
                onChange={(e) => setType(e.target.value as ObservationType)}>
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </label>
      <label>How long after you made it? (minutes)
        <input data-testid="observation-minutes" value={minutes}
               onChange={(e) => setMinutes(e.target.value)} />
      </label>
      {type === 'food_texture' && (
        <label>Which food?
          <select data-testid="observation-food" value={foodId}
                  onChange={(e) => setFoodId(e.target.value)}>
            {applicationFoods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
      )}
      <label>Score
        <select data-testid="observation-score" value={score}
                onChange={(e) => setScore(e.target.value)}>
          {SCALE.map((label, index) => (
            <option key={label} value={index + 1}>{label}</option>
          ))}
        </select>
      </label>
      <label>In your words
        <textarea data-testid="observation-text" value={text}
                  onChange={(e) => setText(e.target.value)} />
      </label>
      <label>
        <input type="checkbox" data-testid="observation-control" checked={control}
               onChange={(e) => setControl(e.target.checked)} />
        I compared it against an undressed portion
      </label>
      <label>
        <input type="checkbox" data-testid="observation-blinded" checked={blinded}
               onChange={(e) => setBlinded(e.target.checked)} />
        Someone else handed it to me without telling me which was which
      </label>
      <p className="blurb">
        Either box makes this record a little stronger — it is still one person in a
        kitchen, and the report says so.
      </p>
      <button type="submit" data-testid="save-observation" disabled={busy}>
        {busy ? 'Saving…' : 'Save this record'}
      </button>
    </form>
  )
}
