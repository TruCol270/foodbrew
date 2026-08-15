import { useState } from 'react'

import type { Suggestion } from '../api/types'

const GROUP_TITLES: Record<string, string> = {
  applicable: 'Changes you can apply',
  note: 'Things to decide or to ask a supplier',
}

/** Spec §7 — never presented as pre-cleared: applying one re-runs every rule. */
export function VariantSuggestions({ suggestions, onApply }: {
  suggestions: Suggestion[]
  onApply: (suggestionId: number) => Promise<void>
}) {
  const [busy, setBusy] = useState<number | null>(null)
  const applicable = suggestions.filter((s) => s.is_applicable)
  const notes = suggestions.filter((s) => !s.is_applicable)

  if (suggestions.length === 0) return null

  async function apply(id: number) {
    setBusy(id)
    try {
      await onApply(id)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section data-testid="variant-suggestions">
      <h3>{GROUP_TITLES.applicable}</h3>
      <p className="blurb">
        None of these is pre-cleared. Applying one copies this formulation, makes the
        change, and runs every rule again — its own flags are shown then.
      </p>
      <ul>
        {applicable.map((suggestion) => (
          <li key={suggestion.id} data-testid={`suggestion-${suggestion.id}`}>
            <div>{suggestion.description}</div>
            <small className="blurb">Raised by {suggestion.raised_by.join(', ')}</small>
            <button type="button" disabled={busy !== null}
                    data-testid={`apply-${suggestion.id}`}
                    onClick={() => apply(suggestion.id)}>
              {busy === suggestion.id ? 'Running…' : 'Apply and compare'}
            </button>
          </li>
        ))}
      </ul>

      {notes.length > 0 && (
        <>
          <h3>{GROUP_TITLES.note}</h3>
          <ul data-testid="suggestion-notes">
            {notes.map((suggestion) => (
              <li key={suggestion.id}>
                <div>{suggestion.description}</div>
                <small className="blurb">Raised by {suggestion.raised_by.join(', ')}</small>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
