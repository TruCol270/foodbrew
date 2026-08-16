import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { DoseCards } from '../components/DoseCards'
import { EnvelopePanel } from '../components/EnvelopePanel'
import { FindingGroups } from '../components/FindingGroups'
import { FormatRecommendationPanel } from '../components/FormatRecommendation'
import { GiStrip } from '../components/GiStrip'
import { StaleBanner } from '../components/StaleBanner'
import { VariantSuggestions } from '../components/VariantSuggestions'
import { HeadlineBadge } from '../components/VerdictBadge'
import type { Evaluation } from '../api/types'

export default function Verdict() {
  const { evaluationId } = useParams()
  const navigate = useNavigate()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!evaluationId) return
    api.evaluation(evaluationId).then(setEvaluation).catch((e) => setError(e.message))
  }, [evaluationId])

  const rerun = useCallback(async () => {
    if (!evaluation) return
    setError(null)
    try {
      const fresh = await api.evaluate(evaluation.formulation_id)
      navigate(`/evaluations/${fresh.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [evaluation, navigate])

  const applyVariant = useCallback(async (suggestionId: number) => {
    if (!evaluation) return
    setError(null)
    try {
      const applied = await api.applyVariant(evaluation.id, suggestionId)
      // Workflow C: land in the comparison, not on a bare new verdict.
      navigate(`/compare?ids=${evaluation.id}&ids=${applied.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [evaluation, navigate])

  const startTrial = useCallback(async () => {
    if (!evaluation) return
    setError(null)
    try {
      const trial = await api.startTrial(evaluation.id)
      navigate(`/trials/${trial.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [evaluation, navigate])

  if (error) return <p className="error">{error}</p>
  if (!evaluation) return <p>Loading…</p>

  return (
    <>
      <h1>Verdict</h1>
      {evaluation.stale && <StaleBanner changes={evaluation.changes} onRerun={rerun} />}
      <HeadlineBadge headline={evaluation.headline} />
      <p className="blurb">
        Run {evaluation.created_at.slice(0, 16).replace('T', ' ')} on engine{' '}
        {evaluation.engine_version}. This is a record of that run: editing a
        record afterwards does not change it. Re-run to see the effect of a change.
      </p>
      <p className="no-print">
        <Link to={`/evaluations/${evaluation.id}/report`}>Open the printable report</Link>
      </p>

      <FindingGroups
        blockers={evaluation.blockers}
        dataGaps={evaluation.data_gaps}
        cautions={evaluation.cautions}
        advisories={evaluation.advisories}
      />

      <DoseCards cards={evaluation.dose_cards} />
      <GiStrip lanes={evaluation.gi_strip} />
      <EnvelopePanel envelope={evaluation.envelope} observed={evaluation.observed} />
      <FormatRecommendationPanel recommendation={evaluation.format_recommendation} />
      <VariantSuggestions suggestions={evaluation.suggestions} onApply={applyVariant} />

      <p className="no-print">
        {evaluation.trial_ids.length === 0 ? (
          <button type="button" data-testid="start-trial" onClick={startTrial}>
            Plan a kitchen trial for this
          </button>
        ) : (
          <>
            <Link to={`/trials/${evaluation.trial_ids[0]}`} data-testid="open-trial">
              Open the kitchen trial
            </Link>{' '}
            <button type="button" data-testid="start-trial" onClick={startTrial}>
              Start another trial
            </button>
          </>
        )}
      </p>
    </>
  )
}
