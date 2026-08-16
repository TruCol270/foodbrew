import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { BatchForm } from '../components/BatchForm'
import { ObservationForm } from '../components/ObservationForm'
import { ObservedList } from '../components/ObservedList'
import { ProtocolChecklist } from '../components/ProtocolChecklist'
import { SymptomForm } from '../components/SymptomForm'
import type { Food, Formulation, Trial as TrialType } from '../api/types'

/** Spec §10 screen 6 — protocol, batch log, quick-entry forms, meals. */
export default function Trial() {
  const { trialId } = useParams()
  const [trial, setTrial] = useState<TrialType | null>(null)
  const [formulation, setFormulation] = useState<Formulation | null>(null)
  const [foods, setFoods] = useState<Food[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!trialId) return
    api.trial(trialId).then(setTrial).catch((e) => setError(e.message))
  }, [trialId])

  useEffect(() => {
    if (!trial) return
    Promise.all([api.formulation(trial.formulation_id), api.foods()])
      .then(([f, all]) => { setFormulation(f); setFoods(all) })
      .catch((e) => setError(e.message))
  }, [trial])

  const batch = trial?.batches.at(-1) ?? null

  const applicationFoods = useMemo(
    () => foods.filter((f) => formulation?.application_food_ids.includes(f.id)),
    [foods, formulation],
  )
  const triggerFoods = useMemo(
    () => foods.filter((f) => formulation?.target_trigger_food_ids.includes(f.id)),
    [foods, formulation],
  )

  const guard = useCallback(async (run: () => Promise<TrialType>) => {
    setError(null)
    try {
      setTrial(await run())
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  if (error) return <p className="error" data-testid="trial-error">{error}</p>
  if (!trial) return <p>Loading…</p>

  const terminal = trial.status === 'complete' || trial.status === 'abandoned'

  return (
    <>
      <h1>Kitchen trial</h1>
      <p className="blurb">
        Testing <Link to={`/evaluations/${trial.evaluation_id}`}>this verdict</Link>.
        Status: <span data-testid="trial-status">{trial.status}</span>. Nothing you
        record here changes what the rules predicted — it is stored beside it.
      </p>

      <ProtocolChecklist
        checkpoints={trial.protocol.checkpoints}
        batch={batch}
        notes={trial.protocol.notes}
      />

      {terminal ? (
        <p data-testid="trial-closed">
          This trial is {trial.status}. Everything recorded stays here; start a new
          trial from the verdict screen to record anything else.
        </p>
      ) : (
        <>
          <BatchForm onSubmit={(body) => guard(() => api.addBatch(trial.id, body))} />
          {batch && (
            <>
              <ObservationForm
                applicationFoods={applicationFoods}
                onSubmit={(body) => guard(() => api.addObservation(batch.id, body))}
              />
              <SymptomForm
                batchId={batch.id}
                triggerFoods={triggerFoods}
                onSubmit={(body) => guard(() => api.addSymptomEntry(batch.id, body))}
              />
            </>
          )}
          <p className="no-print">
            <button type="button" data-testid="complete-trial"
                    onClick={() => guard(() => api.setTrialStatus(trial.id, 'complete'))}>
              Mark this trial complete
            </button>{' '}
            <button type="button" data-testid="abandon-trial"
                    onClick={() => guard(() => api.setTrialStatus(trial.id, 'abandoned'))}>
              Stop this trial
            </button>
          </p>
        </>
      )}

      <ObservedList
        observations={trial.batches.flatMap((b) => b.observations)}
        symptoms={trial.batches.flatMap((b) => b.symptom_entries)}
      />

      <p className="no-print">
        <Link to={`/evaluations/${trial.evaluation_id}/report`}>
          Open the report with these results in it
        </Link>
      </p>
    </>
  )
}
