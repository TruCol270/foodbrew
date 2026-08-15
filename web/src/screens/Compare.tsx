import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { ComparisonTable } from '../components/ComparisonTable'
import type { Comparison } from '../api/types'

/** Spec §3 Workflow B — one column per variant, changed cells highlighted. */
export default function Compare() {
  const [params] = useSearchParams()
  const ids = params.getAll('ids')
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [changedOnly, setChangedOnly] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (ids.length < 2) {
      setError('Pick at least two evaluations to compare.')
      return
    }
    api.compare(ids).then(setComparison).catch((e) => setError(e.message))
    // ids is a fresh array each render; the joined string is the real dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids.join(',')])

  if (error) return <p className="error">{error}</p>
  if (!comparison) return <p>Loading…</p>

  return (
    <>
      <h1>Compare variants</h1>
      <p className="blurb">
        A row that is present on one side and absent on another reads "not in this
        variant" rather than disappearing — that difference is usually the point.
      </p>
      <label>
        <input type="checkbox" checked={changedOnly} data-testid="changed-only"
               onChange={(e) => setChangedOnly(e.target.checked)} />
        Show only what changed
      </label>

      <ComparisonTable comparison={comparison} changedOnly={changedOnly} />

      <ul>
        {comparison.columns.map((column) => (
          <li key={column.evaluation_id}>
            <Link to={`/evaluations/${column.evaluation_id}`}>{column.label}</Link>
          </li>
        ))}
      </ul>
    </>
  )
}
