import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { EvaluationSummary, Recipe, TrialSummary } from '../api/types'

export default function Home() {
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [evaluations, setEvaluations] = useState<EvaluationSummary[]>([])
  const [trials, setTrials] = useState<TrialSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.recipes(), api.recentEvaluations(), api.activeTrials()])
      .then(([r, e, t]) => { setRecipes(r); setEvaluations(e); setTrials(t) })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="error">{error}</p>

  return (
    <>
      <h1>Your recipes</h1>
      {recipes.length === 0 ? (
        <p>Nothing yet. <Link to="/recipes/new">Build your first recipe</Link>.</p>
      ) : (
        <table>
          <thead><tr><th>Recipe</th><th>Ingredients</th><th>Created</th></tr></thead>
          <tbody>
            {recipes.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/recipes/${r.id}`}>{r.name}</Link></td>
                <td>{r.ingredients.length}</td>
                <td>{r.created_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Recent verdicts</h2>
      {evaluations.length === 0 ? (
        <p>No formulation has been evaluated yet.</p>
      ) : (
        <table>
          <thead><tr><th>Verdict</th><th>Run</th><th>Engine</th></tr></thead>
          <tbody>
            {evaluations.map((e) => (
              <tr key={e.id}>
                <td>
                  <Link to={`/evaluations/${e.id}`} className={`headline--${e.headline.toLowerCase()}`}>
                    {e.headline}
                  </Link>
                </td>
                <td>{e.created_at.slice(0, 16).replace('T', ' ')}</td>
                <td>{e.engine_version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Trials running</h2>
      {trials.length === 0 ? (
        <p>No kitchen trial is open. Start one from a verdict.</p>
      ) : (
        <table data-testid="active-trials">
          <thead><tr><th>Trial</th><th>Batches</th><th>Recorded</th><th>Due now</th></tr></thead>
          <tbody>
            {trials.map((t) => (
              <tr key={t.id}>
                <td><Link to={`/trials/${t.id}`}>{t.status}</Link></td>
                <td>{t.batch_count}</td>
                <td>{t.observation_count}</td>
                <td>{t.due_checkpoint_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
