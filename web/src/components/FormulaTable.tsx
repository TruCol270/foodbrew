import type { Formula, ProcessLine } from '../api/types'
import { TruthValue } from './TruthValue'

/** Percent of total batch weight, in order of addition (plan decisions #6, #7). */
export function FormulaTable({ formula, process }: {
  formula: Formula
  process: ProcessLine[]
}) {
  return (
    <section data-testid="formula">
      <h3>Formula</h3>
      <p className="blurb">
        Percent of total batch weight, in the order the ingredients go in. The
        percentages are the formula; the grams are one batch of it. Percent is
        calculated from the weights, so the two cannot disagree.
      </p>
      <div className="table-scroll">
        <table data-testid="formula-table">
          <thead>
            <tr>
              <th>#</th><th>Ingredient</th><th>% of total</th><th>Grams</th>
              <th>pH</th><th>Water</th><th>Allergens</th>
            </tr>
          </thead>
          <tbody>
            {formula.lines.map((line) => (
              <tr key={line.food_id} data-testid={`formula-${line.food_id}`}>
                <td>{line.position}</td>
                <th scope="row">{line.food_name}</th>
                <td>{line.percent_of_total === null ? '—' : line.percent_of_total}</td>
                <td>{line.amount_g}</td>
                <td><TruthValue tracked={line.ph} /></td>
                <td><TruthValue tracked={line.water_content_pct} unit="%" /></td>
                <td>{line.allergens.length ? line.allergens.join(', ') : 'not recorded'}</td>
              </tr>
            ))}
            <tr data-testid="formula-total">
              <td /><th scope="row">Total</th>
              <td><strong>{formula.printed_percent_total ?? '—'}</strong></td>
              <td><strong>{formula.total_g}</strong></td>
              <td /><td /><td />
            </tr>
          </tbody>
        </table>
      </div>
      {formula.printed_percent_total !== null && formula.printed_percent_total !== 100 && (
        <p className="blurb">
          The printed percentages total {formula.printed_percent_total} rather than 100
          because each is rounded to two decimals. The grams are exact.
        </p>
      )}

      {process.length > 0 && (
        <>
          <h4>Process</h4>
          <div className="table-scroll">
            <table data-testid="process">
              <thead>
                <tr><th>Step</th><th>Operation</th><th>Heat</th><th>Enzyme added here</th></tr>
              </thead>
              <tbody>
                {process.map((step) => (
                  <tr key={step.order}>
                    <td>{step.order}</td>
                    <th scope="row">{step.label}</th>
                    <td>{step.is_heat ? 'yes' : 'no'}</td>
                    <td>{step.is_enzyme_addition_point ? 'yes' : 'no'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
