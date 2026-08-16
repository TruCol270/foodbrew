import { useState } from 'react'

const CLASSES = ['pectin_cellulose', 'structural_protein', 'starch'] as const
const TIERS = ['unconfirmed', 'gradual', 'rapid'] as const

const CLASS_TEXT: Record<string, string> = {
  pectin_cellulose: 'plant cell wall and pectin',
  structural_protein: 'structural protein',
  starch: 'starch',
}

const TIER_TEXT: Record<string, string> = {
  unconfirmed: 'not established — reports cannot assess',
  gradual: 'gradual — fine at the table, softening over hours',
  rapid: 'rapid — softening within the hour',
}

/**
 * Spec §15 item 4's answer, enterable. The tier IS the provenance (decision
 * #4): moving an entry off `unconfirmed` is what turns R15's cannot_assess into
 * a verdict, so this editor is the shortest path between a supplier's answer
 * and a formulation the tool can judge.
 */
export function StructuralEditor({ entries, onSave }: {
  entries: { structural_class: string; tier: string }[]
  onSave: (value: { structural_class: string; tier: string }[]) => Promise<void>
}) {
  const [draft, setDraft] = useState(entries)
  const [busy, setBusy] = useState(false)

  function setTier(structuralClass: string, tier: string) {
    setDraft((current) => {
      const without = current.filter((e) => e.structural_class !== structuralClass)
      return tier === '' ? without : [...without, { structural_class: structuralClass, tier }]
    })
  }

  return (
    <div data-testid="structural-editor">
      <p className="blurb">
        What this enzyme does to the structure of the food it lands on. Leave a class
        unset if it does not act on it at all; mark it <em>not established</em> if
        nobody has told you yet — the tool then declines to judge rather than guessing.
      </p>
      {CLASSES.map((structuralClass) => {
        const current = draft.find((e) => e.structural_class === structuralClass)
        return (
          <label key={structuralClass}>
            {CLASS_TEXT[structuralClass]}
            <select
              data-testid={`structural-${structuralClass}`}
              value={current?.tier ?? ''}
              onChange={(e) => setTier(structuralClass, e.target.value)}
            >
              <option value="">does not act on this</option>
              {TIERS.map((tier) => (
                <option key={tier} value={tier}>{TIER_TEXT[tier]}</option>
              ))}
            </select>
          </label>
        )
      })}
      <button
        type="button"
        data-testid="save-structural"
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          try {
            await onSave(draft)
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? 'Saving…' : 'Save what it degrades'}
      </button>
    </div>
  )
}
