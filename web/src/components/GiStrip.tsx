import type { GiLane } from '../api/types'
import { TruthValue } from './TruthValue'

/** Spec §10 screen 4 — the deck's slide-3 visual, rendered from live data. */
export function GiStrip({ lanes }: { lanes: GiLane[] }) {
  if (lanes.length === 0) return null
  const regions = lanes[0]!.regions

  return (
    <section data-testid="gi-strip">
      <h3>Where each enzyme can work</h3>
      <p className="blurb">
        A deadline, not a target: anything left when the food reaches the colon
        ferments there. The mouth is shown greyed because food is there for
        seconds — too short for any enzyme to act.
      </p>
      <table>
        <thead>
          <tr>
            <th>Enzyme</th>
            {regions.map((r) => (
              <th key={r.region_id} className={r.dormant ? 'region--dormant' : undefined}>
                {r.name}<br /><small>pH {r.ph_low}–{r.ph_high}</small>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lanes.map((lane) => (
            <tr key={lane.enzyme_id}>
              <th scope="row">
                {lane.enzyme_name}<br />
                <small>
                  active pH <TruthValue tracked={lane.ph_min} />–<TruthValue tracked={lane.ph_max} />
                </small>
              </th>
              {lane.regions.map((r) => (
                <td
                  key={r.region_id}
                  data-testid={`cell-${lane.enzyme_id}-${r.region_id}`}
                  className={[
                    r.active ? 'cell--active' : 'cell--inactive',
                    r.before_deadline ? '' : 'cell--past-deadline',
                  ].join(' ')}
                >
                  {r.dormant
                    ? 'dormant'
                    : r.active
                      ? (r.before_deadline ? 'active' : 'active — past deadline')
                      : '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
