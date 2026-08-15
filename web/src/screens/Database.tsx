import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { TruthValue } from '../components/TruthValue'
import type { Enzyme, Food, Proposal, Tracked } from '../api/types'

/** The fields `store/records.py` will accept. Keep the two lists in step. */
const ENZYME_FIELDS = [
  'ph_min', 'ph_max', 'ph_opt_low', 'ph_opt_high', 'ph_shelf_stable_min',
  'temp_min_c', 'temp_max_c', 'temp_opt_c',
  'dose_min', 'dose_max', 'dose_evidence_threshold',
] as const
const FOOD_FIELDS = ['ph', 'water_content_pct', 'typical_load_value'] as const

function FieldRow({ name, tracked, onSave }: {
  name: string
  tracked: Tracked
  onSave: (value: number | null) => void
}) {
  const [draft, setDraft] = useState(tracked.value === null ? '' : String(tracked.value))
  useEffect(() => { setDraft(tracked.value === null ? '' : String(tracked.value)) },
            [tracked.value])

  return (
    <div className="editor-field">
      <label htmlFor={`field-${name}`}>{name}</label>
      <input id={`field-${name}`} data-testid={`field-${name}`} value={draft}
             onChange={(e) => setDraft(e.target.value)} />
      <span>
        <TruthValue tracked={tracked} />{' '}
        <button type="button" data-testid={`save-${name}`}
                onClick={() => onSave(draft === '' ? null : Number(draft))}>
          Save
        </button>
      </span>
    </div>
  )
}

/** The client carries `createProposal`, and the exit walk asks the founder to
 * raise one from the screen, but nothing else in the plan's file list calls
 * it — the inbox below only lists what already exists. Filed here, next to
 * the inbox it feeds, so the "confirmed" path has an on-screen way in. */
function NewProposalForm({ tables, onSubmit }: {
  tables: { table_name: 'enzyme' | 'food'; record_id: string; field: string }
  onSubmit: (proposal: {
    table_name: string; record_id: string; field: string
    proposed_value: string; source_citation: string
  }) => Promise<void>
}) {
  const [draft, setDraft] = useState({
    table_name: tables.table_name, record_id: tables.record_id, field: tables.field,
    proposed_value: '', source_citation: '',
  })
  useEffect(() => {
    setDraft((prev) => ({
      ...prev, table_name: tables.table_name, record_id: tables.record_id, field: tables.field,
    }))
  }, [tables.table_name, tables.record_id, tables.field])

  return (
    <form onSubmit={(e) => {
      e.preventDefault()
      onSubmit(draft).then(() => setDraft((prev) => ({ ...prev, proposed_value: '', source_citation: '' })))
    }}>
      <label>
        Table
        <select value={draft.table_name} data-testid="proposal-table"
                onChange={(e) => setDraft({ ...draft, table_name: e.target.value as 'enzyme' | 'food' })}>
          <option value="enzyme">enzyme</option>
          <option value="food">food</option>
        </select>
      </label>
      <label>
        Record id
        <input value={draft.record_id} data-testid="proposal-record-id"
               onChange={(e) => setDraft({ ...draft, record_id: e.target.value })} />
      </label>
      <label>
        Field
        <input value={draft.field} data-testid="proposal-field"
               onChange={(e) => setDraft({ ...draft, field: e.target.value })} />
      </label>
      <label>
        Proposed value
        <input value={draft.proposed_value} data-testid="proposal-value"
               onChange={(e) => setDraft({ ...draft, proposed_value: e.target.value })} />
      </label>
      <label>
        Source citation
        <input value={draft.source_citation} data-testid="proposal-citation"
               onChange={(e) => setDraft({ ...draft, source_citation: e.target.value })} />
      </label>
      <button type="submit" data-testid="submit-proposal">Send to the inbox</button>
    </form>
  )
}

export default function Database() {
  const [enzymes, setEnzymes] = useState<Enzyme[]>([])
  const [foods, setFoods] = useState<Food[]>([])
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [enzymeId, setEnzymeId] = useState('')
  const [foodId, setFoodId] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    const [e, f, p] = await Promise.all([api.enzymes(), api.foods(), api.proposals()])
    setEnzymes(e); setFoods(f); setProposals(p)
    if (!enzymeId && e.length) setEnzymeId(e[0]!.id)
    if (!foodId && f.length) setFoodId(f[0]!.id)
  }

  useEffect(() => { reload().catch((e) => setError(e.message)) }, [])

  const enzyme = enzymes.find((e) => e.id === enzymeId)
  const food = foods.find((f) => f.id === foodId)

  async function run(work: () => Promise<unknown>) {
    setError(null)
    try { await work(); await reload() } catch (e) { setError((e as Error).message) }
  }

  return (
    <>
      <h1>Database</h1>
      {error && <p className="error" data-testid="database-error">{error}</p>}
      <p className="blurb">
        Anything you type here is stored as your own value and labelled that way. A
        value only becomes confirmed through the inbox below, where it arrives with a
        source. Editing a record never changes an evaluation that has already run —
        those runs will show a banner asking you to re-run.
      </p>

      <fieldset>
        <legend>Enzymes</legend>
        <select value={enzymeId} data-testid="enzyme-picker"
                onChange={(e) => setEnzymeId(e.target.value)}>
          {enzymes.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        {enzyme && (
          <>
            {ENZYME_FIELDS.map((name) => (
              <FieldRow key={name} name={name} tracked={enzyme[name]}
                        onSave={(value) => run(() => api.updateEnzyme(enzyme.id, { [name]: value }))} />
            ))}
            <button type="button" data-testid="reset-enzyme"
                    onClick={() => run(() => api.resetEnzyme(enzyme.id))}>
              Reset this enzyme to the shipped values
            </button>
          </>
        )}
      </fieldset>

      <fieldset>
        <legend>Foods</legend>
        <select value={foodId} data-testid="food-record-picker"
                onChange={(e) => setFoodId(e.target.value)}>
          {foods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        {food && (
          <>
            {FOOD_FIELDS.map((name) => (
              <FieldRow key={name} name={name} tracked={food[name]}
                        onSave={(value) => run(() => api.updateFood(food.id, { [name]: value }))} />
            ))}
            <button type="button" data-testid="reset-food"
                    onClick={() => run(() => api.resetFood(food.id))}>
              Reset this food to the shipped values
            </button>
          </>
        )}
      </fieldset>

      <fieldset>
        <legend>Propose a confirmed value</legend>
        <p className="blurb">
          Raise a value with a source citation. It sits in the inbox below until you
          approve or reject it — nothing here writes to the record directly.
        </p>
        <NewProposalForm
          tables={{ table_name: 'enzyme', record_id: enzymeId, field: '' }}
          onSubmit={(proposal) => run(() => api.createProposal(proposal))}
        />
      </fieldset>

      <fieldset>
        <legend>Proposals waiting on you</legend>
        <p className="blurb">
          Each one carries a source. Approving records the value as confirmed with that
          source attached; rejecting changes nothing and keeps the record of the decision.
        </p>
        {proposals.length === 0 ? (
          <p>Nothing waiting.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Record</th><th>Field</th><th>Value</th><th>Source</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {proposals.map((proposal) => (
                <tr key={proposal.id} data-testid={`proposal-${proposal.id}`}>
                  <td>{proposal.table_name} {proposal.record_id}</td>
                  <td>{proposal.field}</td>
                  <td>{proposal.proposed_value}</td>
                  <td>{proposal.source_citation}</td>
                  <td>{proposal.status}</td>
                  <td>
                    {proposal.status === 'pending' && (
                      <>
                        <button type="button" data-testid={`approve-${proposal.id}`}
                                onClick={() => run(() => api.approveProposal(proposal.id))}>
                          Approve
                        </button>
                        <button type="button"
                                onClick={() => run(() => api.rejectProposal(proposal.id))}>
                          Reject
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </fieldset>
    </>
  )
}
