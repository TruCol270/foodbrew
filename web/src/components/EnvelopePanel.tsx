import type { DwellProfile, Verdict } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

/** Spec §6.3 — the three occasions, with the dwell ranges that define them. */
const OCCASIONS: { profile: DwellProfile; title: string; blurb: string }[] = [
  { profile: 'immediate', title: 'Dressed at the table', blurb: 'Eaten within the hour' },
  { profile: 'packed', title: 'Packed ahead', blurb: 'Dressed 1 to 8 hours before eating' },
  { profile: 'marinade', title: 'Marinade', blurb: 'Left 8 hours or more, on purpose' },
]

export function EnvelopePanel({ envelope }: { envelope: Record<DwellProfile, Verdict> }) {
  return (
    <section data-testid="envelope-panel">
      <h3>Which occasions this can support</h3>
      <p className="blurb">
        What the dressing does to the food it sits on, by how long it sits there.
        An occasion you do not intend to sell is still shown, so nothing is hidden.
      </p>
      <table>
        <tbody>
          {OCCASIONS.map(({ profile, title, blurb }) => (
            <tr key={profile} data-testid={`occasion-${profile}`}>
              <th scope="row">{title}<br /><small>{blurb}</small></th>
              <td><VerdictBadge verdict={envelope[profile]} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
