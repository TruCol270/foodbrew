import type { BatchRecord } from '../api/types'

/** The batch record — the first document reviewed when a batch misses spec. */
export function BatchRecords({ batches }: { batches: BatchRecord[] }) {
  if (batches.length === 0) return null
  return (
    <section data-testid="batch-records">
      <h3>Batch records</h3>
      <p className="blurb">
        What was actually made, as it was made. Blank cells are parameters that were
        not recorded for that batch.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Made</th><th>Size</th><th>pH</th><th>Minutes</th><th>Difficulty</th>
              <th>Enzyme after step</th><th>Enzyme source</th><th>Storage</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((b) => (
              <tr key={b.made_at}>
                <th scope="row">{b.made_at.slice(0, 16).replace('T', ' ')}</th>
                <td>{b.batch_size_g === null ? '' : `${b.batch_size_g} g`}</td>
                <td>{b.measured_ph === null ? 'not measured' : `${b.measured_ph} (${b.ph_method})`}</td>
                <td>{b.make_minutes ?? ''}</td>
                <td>{b.difficulty_score === null ? '' : `${b.difficulty_score} of 5`}</td>
                <td>{b.enzyme_addition_step ?? ''}</td>
                <td>{b.enzyme_source_note || 'not recorded'}</td>
                <td>{b.storage_mode}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {batches.filter((b) => b.process_notes).map((b) => (
        <blockquote key={`${b.made_at}-notes`}>{b.process_notes}</blockquote>
      ))}
    </section>
  )
}
