import type { Finding } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

function Group({ title, blurb, findings, open }: {
  title: string; blurb: string; findings: Finding[]; open: boolean
}) {
  if (findings.length === 0) return null
  return (
    <details
      className="finding-group"
      open={open}
      data-testid={`group-${title.toLowerCase().replace(/\s/g, '-')}`}
    >
      <summary>
        {title}
        <span className="count-badge">{findings.length}</span>
      </summary>
      <div className="finding-group__body">
        <p className="blurb">{blurb}</p>
        <ul>
          {findings.map((f, i) => (
            <li key={`${f.rule_id}-${f.enzyme_id ?? ''}-${f.food_id ?? ''}-${i}`}>
              <strong>{f.rule_id} — {f.rule_title}</strong> <VerdictBadge verdict={f.verdict} />
              <div>{f.message}</div>
            </li>
          ))}
        </ul>
      </div>
    </details>
  )
}

export function FindingGroups({
  blockers, dataGaps, cautions, advisories,
}: {
  blockers: Finding[]; dataGaps: Finding[]; cautions: Finding[]; advisories: Finding[]
}) {
  return (
    <>
      <Group title="Blockers" open blurb="These stop the formulation as specified."
             findings={blockers} />
      <Group title="Data gaps" open
             blurb="Missing values. Fill these in and re-run to get a verdict."
             findings={dataGaps} />
      <Group title="Cautions" open={false}
             blurb="Not blockers, but they change over time or with use."
             findings={cautions} />
      <Group title="Advisory" open={false}
             blurb="Notes that never change the headline — your call to make."
             findings={advisories} />
    </>
  )
}
