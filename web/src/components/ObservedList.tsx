import type { Observation, SymptomEntry } from '../api/types'

const CLASS_TITLES: Record<string, string> = {
  finding: 'Findings — your answer is the data',
  observation: 'Observations — watched, not controlled',
  hypothesis: 'Hypotheses — for a food scientist to test properly',
}

/** Spec §6.6, on screen: the same three words the report uses. */
export function ObservedList({ observations, symptoms }: {
  observations: Observation[]
  symptoms: SymptomEntry[]
}) {
  const grouped = {
    finding: observations.filter((o) => o.export_class === 'finding'),
    observation: observations.filter((o) => o.export_class === 'observation'),
  }

  return (
    <section data-testid="observed-list">
      <h3>What you have recorded</h3>
      {(['finding', 'observation'] as const).map((key) => (
        <div key={key}>
          <h4>{CLASS_TITLES[key]}</h4>
          {grouped[key].length === 0 ? (
            <p className="blurb">Nothing in this group yet.</p>
          ) : (
            <ul data-testid={`observed-${key}`}>
              {grouped[key].map((o) => (
                <li key={o.id}>
                  <strong>{o.type.replace('_', ' ')}</strong>
                  {o.application_food_id && ` on ${o.application_food_id}`} —{' '}
                  {o.dwell_bucket}
                  {o.score !== null && `, scored ${o.score} of 5`}{' '}
                  <small className="blurb">({o.confidence_tier})</small>
                  {o.free_text && <blockquote>{o.free_text}</blockquote>}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}

      <h4>{CLASS_TITLES.hypothesis}</h4>
      {symptoms.length === 0 ? (
        <p className="blurb">No meal logged yet.</p>
      ) : (
        <ul data-testid="observed-hypothesis">
          {symptoms.map((entry) => (
            <li key={entry.id}>
              <strong>{entry.computed_dose.trigger_food_name}</strong>
              {entry.amount_value !== null && ` — ${entry.amount_value} ${entry.amount_unit}`}
              {entry.outcome_score !== null && `, outcome ${entry.outcome_score} of 5`}
              <ul>
                {entry.computed_dose.enzymes.map((dose) => (
                  <li key={dose.enzyme_id}>
                    {dose.units_delivered === null
                      ? `${dose.enzyme_name}: dose could not be worked out`
                      : `${dose.enzyme_name}: ${dose.units_delivered} ${dose.dose_unit} delivered` +
                        (dose.meets_threshold === null
                          ? ' — no threshold recorded to compare with'
                          : dose.meets_threshold
                            ? ' — clears the evidence threshold'
                            : ' — below the evidence threshold')}
                  </li>
                ))}
              </ul>
              {entry.notes && <blockquote>{entry.notes}</blockquote>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
