import type { DoseCard } from '../api/types'
import { TruthValue } from './TruthValue'

export function DoseCards({ cards }: { cards: DoseCard[] }) {
  if (cards.length === 0) return null
  return (
    <section data-testid="dose-cards">
      <h3>Dose per serving</h3>
      <p className="blurb">
        Dose is driven by how much of the substrate a serving carries, not by the
        weight of the food. Below the evidence threshold, an enzyme behaves like a
        placebo — which is why an under-dose is flagged rather than rounded up.
      </p>
      {cards.map((card) => (
        <article key={card.enzyme_id} className="dose-card"
                 data-testid={`dose-card-${card.enzyme_id}`}>
          <h4>{card.enzyme_name}</h4>
          <dl>
            <dt>Your dose</dt>
            <dd>{card.dose === null ? 'not set' : `${card.dose} ${card.dose_unit}`}</dd>
            <dt>Benchmark range</dt>
            <dd>
              <TruthValue tracked={card.dose_min} unit={card.dose_unit} />
              {' – '}
              <TruthValue tracked={card.dose_max} unit={card.dose_unit} />
            </dd>
            <dt>Evidence threshold</dt>
            <dd><TruthValue tracked={card.dose_evidence_threshold} unit={card.dose_unit} /></dd>
            <dt>Substrate in one serving</dt>
            <dd><TruthValue tracked={card.substrate_load} /></dd>
            <dt>Clears the threshold</dt>
            <dd>
              {card.meets_threshold === null
                ? 'cannot tell — see the values above'
                : card.meets_threshold ? 'yes' : 'no'}
              {card.above_benchmark_max && ' — above the benchmark range; it works, but it is an expensive way to solve it'}
            </dd>
          </dl>
        </article>
      ))}
    </section>
  )
}
