import type { Finding } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

function Group({ title, blurb, findings }: {
  title: string; blurb: string; findings: Finding[]
}) {
  if (findings.length === 0) return null
  return (
    <section className="finding-group" data-testid={`group-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <h3>{title}</h3>
      <p className="blurb">{blurb}</p>
      <ul>
        {findings.map((f, i) => (
          <li key={`${f.rule_id}-${f.enzyme_id ?? ''}-${f.food_id ?? ''}-${i}`}>
            <strong>{f.rule_id} — {f.rule_title}</strong> <VerdictBadge verdict={f.verdict} />
            <div>{f.message}</div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function FindingGroups({
  blockers, dataGaps, cautions, advisories,
}: {
  blockers: Finding[]; dataGaps: Finding[]; cautions: Finding[]; advisories: Finding[]
}) {
  return (
    <>
      <Group title="Blockers" blurb="These stop the formulation as specified."
             findings={blockers} />
      <Group title="Data gaps" blurb="Missing values. Fill these in and re-run to get a verdict."
             findings={dataGaps} />
      <Group title="Cautions" blurb="Not blockers, but they change over time or with use."
             findings={cautions} />
      <Group title="Advisory" blurb="Notes that never change the headline — your call to make."
             findings={advisories} />
    </>
  )
}
