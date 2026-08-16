import type { Tracked } from '../api/types'
import { TruthValue } from './TruthValue'

/**
 * What a specification sheet carries that this tool cannot measure. Stating the
 * absence is the convention: an incomplete spec says which parameters are
 * outstanding rather than omitting the rows (spec §12, plan decision #8).
 */
export function FinishedProductParameters({ measuredPh }: { measuredPh: Tracked }) {
  return (
    <section data-testid="finished-product-parameters">
      <h3>Finished-product parameters</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Parameter</th><th>Value</th><th>Basis</th></tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">pH</th>
              <td><TruthValue tracked={measuredPh} /></td>
              <td>measured, or estimated from the lowest-pH wet ingredient</td>
            </tr>
            <tr>
              <th scope="row">Water activity</th>
              <td>not measured</td>
              <td>needs a lab instrument this tool does not model</td>
            </tr>
            <tr>
              <th scope="row">Viscosity</th>
              <td>not measured</td>
              <td>outside the rules this tool evaluates</td>
            </tr>
            <tr>
              <th scope="row">Nutrition</th>
              <td>not calculated</td>
              <td>no nutrient data is held for these ingredients</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
