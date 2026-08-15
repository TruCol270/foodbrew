import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import { DoseCards } from '../components/DoseCards'
import { EnvelopePanel } from '../components/EnvelopePanel'
import { FindingGroups } from '../components/FindingGroups'
import { GiStrip } from '../components/GiStrip'
import { HeadlineBadge } from '../components/VerdictBadge'
import type { Evaluation } from '../api/types'

export default function Verdict() {
  const { evaluationId } = useParams()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!evaluationId) return
    api.evaluation(evaluationId).then(setEvaluation).catch((e) => setError(e.message))
  }, [evaluationId])

  if (error) return <p className="error">{error}</p>
  if (!evaluation) return <p>Loading…</p>

  return (
    <>
      <h1>Verdict</h1>
      <HeadlineBadge headline={evaluation.headline} />
      <p className="blurb">
        Run {evaluation.created_at.slice(0, 16).replace('T', ' ')} on engine{' '}
        {evaluation.engine_version}. This is a record of that run: editing a
        record afterwards does not change it. Re-run to see the effect of a change.
      </p>

      <FindingGroups
        blockers={evaluation.blockers}
        dataGaps={evaluation.data_gaps}
        cautions={evaluation.cautions}
        advisories={evaluation.advisories}
      />

      <DoseCards cards={evaluation.dose_cards} />
      <GiStrip lanes={evaluation.gi_strip} />
      <EnvelopePanel envelope={evaluation.envelope} />
    </>
  )
}
