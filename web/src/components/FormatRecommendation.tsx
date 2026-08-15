import type { FormatRecommendation as Recommendation } from '../api/types'

/** Spec §6.1 R13 — the least separated format that clears the rules checked. */
export function FormatRecommendationPanel({ recommendation }: {
  recommendation: Recommendation
}) {
  return (
    <section data-testid="format-recommendation">
      <h3>Format</h3>
      <p className="blurb">{recommendation.message}</p>
      <table>
        <thead><tr><th>Format</th><th>Blockers</th></tr></thead>
        <tbody>
          {recommendation.options.map((option) => (
            <tr key={option.format} data-testid={`format-option-${option.format}`}
                className={option.format === recommendation.recommended ? 'row--recommended' : undefined}>
              <th scope="row">
                {option.title}
                {option.is_current && <small> — what you have now</small>}
                {option.format === recommendation.recommended && <small> — recommended</small>}
              </th>
              <td>{option.reds.length === 0 ? 'none on the rules checked' : option.reds.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {recommendation.unfixable.length > 0 && (
        <p className="blurb">
          {recommendation.unfixable.join(', ')} stop the formulation however it is
          packaged, so the fix is in the formulation itself rather than in the pack.
        </p>
      )}
    </section>
  )
}
