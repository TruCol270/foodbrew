import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import { AllergenDeclarationPanel } from '../components/AllergenDeclaration'
import { BatchRecords } from '../components/BatchRecords'
import { DoseCards } from '../components/DoseCards'
import { EnvelopePanel } from '../components/EnvelopePanel'
import { FindingGroups } from '../components/FindingGroups'
import { FinishedProductParameters } from '../components/FinishedProductParameters'
import { FormatRecommendationPanel } from '../components/FormatRecommendation'
import { FormulaTable } from '../components/FormulaTable'
import { GiStrip } from '../components/GiStrip'
import { ObservedList } from '../components/ObservedList'
import { TruthValue } from '../components/TruthValue'
import { HeadlineBadge } from '../components/VerdictBadge'
import type { Evaluation, Report as ReportType, Trial as TrialType } from '../api/types'

/** Spec §10 screen 8. The footer disclaimer comes from the layout and prints with it. */
export default function Report() {
  const { evaluationId } = useParams()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [trial, setTrial] = useState<TrialType | null>(null)
  const [report, setReport] = useState<ReportType | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!evaluationId) return
    api.evaluation(evaluationId).then(setEvaluation).catch((e) => setError(e.message))
  }, [evaluationId])

  useEffect(() => {
    if (!evaluationId) return
    api.report(evaluationId).then(setReport).catch((e) => setError(e.message))
  }, [evaluationId])

  useEffect(() => {
    const id = evaluation?.trial_ids[0]
    if (!id) return
    api.trial(id).then(setTrial).catch(() => setTrial(null))
  }, [evaluation])

  if (error) return <p className="error">{error}</p>
  if (!evaluation) return <p>Loading…</p>

  return (
    <>
      <h1>Formulation report</h1>
      <p className="no-print">
        <button type="button" data-testid="print" onClick={() => window.print()}>
          Print or save as PDF
        </button>
        {' '}
        <a href={api.reportUrl(evaluation.id)} data-testid="download-markdown">
          Download the markdown version
        </a>
      </p>

      <HeadlineBadge headline={evaluation.headline} />
      <p className="blurb">
        Evaluation {evaluation.id}, run {evaluation.created_at.slice(0, 16).replace('T', ' ')}{' '}
        on engine {evaluation.engine_version}.
        {evaluation.stale && ' A record it used has changed since; re-run before relying on it.'}
      </p>

      {report && (
        <>
          <section data-testid="identity">
            <h3>Product and formula identity</h3>
            <table>
              <tbody>
                <tr><th scope="row">Product</th><td>{report.recipe_name}</td></tr>
                <tr><th scope="row">Recipe id</th><td>{report.recipe_id || 'not recorded'}</td></tr>
                <tr><th scope="row">Format</th><td>{report.format}</td></tr>
                <tr><th scope="row">Serving size</th>
                    <td>{report.serving_size_g === null ? 'not set' : `${report.serving_size_g} g`}</td></tr>
                <tr><th scope="row">Declared occasion</th>
                    <td>{report.dwell_profile ?? 'not declared'}</td></tr>
                <tr><th scope="row">Measured pH</th>
                    <td><TruthValue tracked={report.measured_ph} /></td></tr>
              </tbody>
            </table>
          </section>
          <FormulaTable formula={report.formula} process={report.process} />
          <AllergenDeclarationPanel declaration={report.allergens} />
          <FinishedProductParameters measuredPh={report.measured_ph} />
        </>
      )}

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

      <section data-testid="observed">
        <h3>What was observed</h3>
        {trial === null ? (
          <p>
            No trial has been recorded for this formulation yet. Everything above is a
            prediction from the rules and the data behind them; nothing here was measured.
          </p>
        ) : (
          <>
            <p className="blurb">
              Trial {trial.id}, {trial.status}. One person, in a kitchen, mostly
              unblinded — each group below says how much weight it carries.
            </p>
            <ObservedList
              observations={trial.batches.flatMap((b) => b.observations)}
              symptoms={trial.batches.flatMap((b) => b.symptom_entries)}
            />
          </>
        )}
      </section>

      {report && <BatchRecords batches={report.batches} />}

      <section>
        <h3>Open questions</h3>
        <ul>
          {evaluation.suggestions
            .filter((s) => s.suggestion_type === 'supplier_question')
            .map((s) => (
              <li key={s.id}>{s.description} <small className="blurb">({s.raised_by.join(', ')})</small></li>
            ))}
        </ul>
      </section>
    </>
  )
}
