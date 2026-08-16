import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { StructuralEditor } from '../components/StructuralEditor'
import { TruthValue } from '../components/TruthValue'
import type { Enzyme, Food, Proposal, Tracked } from '../api/types'

/** The fields `store/records.py` will accept, plus the unit each is measured
 * in. Keep this list and `records.py`'s in step. */
const ENZYME_FIELDS = [
  { field: 'ph_min', label: 'Active pH floor', unit: '' },
  { field: 'ph_max', label: 'Active pH ceiling', unit: '' },
  { field: 'ph_opt_low', label: 'Optimal pH — low end', unit: '' },
  { field: 'ph_opt_high', label: 'Optimal pH — high end', unit: '' },
  { field: 'ph_shelf_stable_min', label: 'Shelf-stable pH floor', unit: '' },
  { field: 'temp_min_c', label: 'Minimum temperature', unit: '°C' },
  { field: 'temp_max_c', label: 'Maximum temperature', unit: '°C' },
  { field: 'temp_opt_c', label: 'Optimal temperature', unit: '°C' },
  { field: 'dose_min', label: 'Minimum dose', unit: '' },
  { field: 'dose_max', label: 'Maximum dose', unit: '' },
  { field: 'dose_evidence_threshold', label: 'Evidence threshold', unit: 'per serving' },
] as const
const FOOD_FIELDS = [
  { field: 'ph', label: 'pH', unit: '' },
  { field: 'water_content_pct', label: 'Water content', unit: '%' },
  { field: 'typical_load_value', label: 'Typical load', unit: '' },
] as const

function FieldRow({ field, label, unit, tracked, onSave }: {
  field: string
  label: string
  unit: string
  tracked: Tracked
  onSave: (value: number | null) => void
}) {
  const [draft, setDraft] = useState(tracked.value === null ? '' : String(tracked.value))
  useEffect(() => { setDraft(tracked.value === null ? '' : String(tracked.value)) },
            [tracked.value])

  // A typo (e.g. "2..5") makes Number(draft) NaN, which JSON.stringify turns
  // into null — Save would then silently wipe a confirmed value to
  // unconfirmed with no error shown. Refuse before that can happen.
  const invalid = draft !== '' && Number.isNaN(Number(draft))

  return (
    <div className="editor-field">
      <label htmlFor={`field-${field}`}>{label}</label>
      <input id={`field-${field}`} data-testid={`field-${field}`} value={draft}
             aria-invalid={invalid}
             onChange={(e) => setDraft(e.target.value)} />
      <span>
        <TruthValue tracked={tracked} unit={unit} showSource />{' '}
        <button type="button" data-testid={`save-${field}`} disabled={invalid}
                onClick={() => onSave(draft === '' ? null : Number(draft))}>
          Save
        </button>
        {invalid && <small className="field-error"> not a number — Save is disabled</small>}
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
  }) => Promise<boolean>
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
      // Only clear the value/citation on a confirmed success — onSubmit
      // resolving isn't that by itself (run() below never rejects), so a
      // failed submit (e.g. server-side validation) used to silently wipe
      // what the founder had just typed.
      onSubmit(draft).then((ok) => {
        if (ok) setDraft((prev) => ({ ...prev, proposed_value: '', source_citation: '' }))
      })
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

  async function run(work: () => Promise<unknown>): Promise<boolean> {
    setError(null)
    try {
      await work()
      await reload()
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    }
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
        {/* One button per record, each carrying its own last-edited status —
            answerable without stepping through the dropdown below, and a
            specific record (e.g. inulinase, whose structural tier §15 item 4
            asks a supplier about) can be reached directly. */}
        <ul className="record-list">
          {enzymes.map((e) => (
            <li key={e.id}>
              <button type="button" data-testid={`record-${e.id}`}
                      onClick={() => setEnzymeId(e.id)}>
                {e.name}
              </button>{' '}
              <span className="blurb" data-testid={`last-edited-${e.id}`}>
                {e.last_edited
                  ? `You last edited this on ${e.last_edited.slice(0, 10)}`
                  : 'Shipped value — you have not edited this record'}
              </span>
            </li>
          ))}
        </ul>
        <select value={enzymeId} data-testid="enzyme-picker"
                onChange={(e) => setEnzymeId(e.target.value)}>
          {enzymes.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        {enzyme && (
          <>
            {ENZYME_FIELDS.map(({ field, label, unit }) => (
              <FieldRow key={field} field={field} label={label} unit={unit}
                        tracked={enzyme[field]}
                        onSave={(value) => run(() => api.updateEnzyme(enzyme.id, { [field]: value }))} />
            ))}
            <StructuralEditor
              key={enzyme.id}
              entries={enzyme.degrades_structural}
              onSave={async (value) => {
                await run(() => api.updateStructured('enzymes', enzyme.id, 'degrades_structural_json', value))
              }}
            />
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
            <p className="blurb" data-testid={`last-edited-${food.id}`}>
              {food.last_edited
                ? `You last edited this on ${food.last_edited.slice(0, 10)}`
                : 'Shipped value — you have not edited this record'}
            </p>
            {FOOD_FIELDS.map(({ field, label, unit }) => (
              <FieldRow key={field} field={field} label={label} unit={unit}
                        tracked={food[field]}
                        onSave={(value) => run(() => api.updateFood(food.id, { [field]: value }))} />
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
