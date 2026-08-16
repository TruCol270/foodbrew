import type { DwellProfile, ObservedEnvelope, Verdict } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

/** Spec §6.3 — the three occasions, with the dwell ranges that define them. */
const OCCASIONS: { profile: DwellProfile; title: string; blurb: string }[] = [
  { profile: 'immediate', title: 'Dressed at the table', blurb: 'Eaten within the hour' },
  { profile: 'packed', title: 'Packed ahead', blurb: 'Dressed 1 to 8 hours before eating' },
  { profile: 'marinade', title: 'Marinade', blurb: 'Left 8 hours or more, on purpose' },
]

export function EnvelopePanel({ envelope, observed }: {
  envelope: Record<DwellProfile, Verdict>
  observed?: ObservedEnvelope | null
}) {
  return (
    <section data-testid="envelope-panel">
      <h3>Which occasions this can support</h3>
      <p className="blurb">
        What the dressing does to the food it sits on, by how long it sits there.
        An occasion you do not intend to sell is still shown, so nothing is hidden.
      </p>
      <table>
        <thead>
          <tr><th /><th>Predicted</th><th>Observed</th></tr>
        </thead>
        <tbody>
          {OCCASIONS.map(({ profile, title, blurb }) => {
            const cell = observed?.profiles[profile]
            return (
              <tr key={profile} data-testid={`occasion-${profile}`}>
                <th scope="row">{title}<br /><small>{blurb}</small></th>
                <td><VerdictBadge verdict={envelope[profile]} /></td>
                <td data-testid={`observed-${profile}`}>
                  {!observed ? (
                    <small className="blurb">no trial yet</small>
                  ) : cell && cell.verdict ? (
                    <>
                      <VerdictBadge verdict={cell.verdict} />{' '}
                      <small className="blurb">({cell.confidence_tier})</small>
                    </>
                  ) : (
                    <small className="blurb">not looked at</small>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {observed && <p className="blurb">{observed.scale_note}</p>}
    </section>
  )
}
