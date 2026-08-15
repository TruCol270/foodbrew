import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Enzyme, Food, Format, ProcessStep, SelectedEnzyme } from '../api/types'

const FORMATS: { value: Format; label: string }[] = [
  { value: 'premixed_wet', label: 'Premixed wet — enzyme stirred into the dressing' },
  { value: 'encapsulated_in_wet', label: 'Encapsulated in wet — capsule inside the dressing' },
  { value: 'dual_chamber', label: 'Dual chamber — wet one side, dry powder the other' },
  { value: 'dry_sachet', label: 'Dry sachet — powder packaged separately' },
]

export default function FormulationSetup() {
  const { recipeId } = useParams()
  const navigate = useNavigate()

  const [enzymeCatalog, setEnzymeCatalog] = useState<Enzyme[]>([])
  const [triggerFoods, setTriggerFoods] = useState<Food[]>([])
  const [applicationFoods, setApplicationFoods] = useState<Food[]>([])

  const [format, setFormat] = useState<Format>('premixed_wet')
  const [targets, setTargets] = useState<string[]>([])
  const [applications, setApplications] = useState<string[]>([])
  const [enzymes, setEnzymes] = useState<SelectedEnzyme[]>([])
  const [servingSize, setServingSize] = useState('30')
  const [measuredPh, setMeasuredPh] = useState('')
  const [steps, setSteps] = useState<ProcessStep[]>([{ order: 1, label: 'Whisk', is_heat: false }])
  const [additionIndex, setAdditionIndex] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([api.enzymes(), api.foods('trigger'), api.foods('application')])
      .then(([e, t, a]) => { setEnzymeCatalog(e); setTriggerFoods(t); setApplicationFoods(a) })
      .catch((err) => setError(err.message))
  }, [])

  // The proposal follows the trigger foods and the format, and stays editable:
  // spec Workflow A step 5 — removing an enzyme does not remove the finding.
  useEffect(() => {
    if (targets.length === 0) { setEnzymes([]); return }
    api.proposedEnzymes(targets, format).then(setEnzymes).catch((e) => setError(e.message))
  }, [targets, format])

  const enzymeById = new Map(enzymeCatalog.map((e) => [e.id, e]))

  function toggle(list: string[], id: string, set: (next: string[]) => void) {
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])
  }

  async function evaluate() {
    setError(null); setBusy(true)
    try {
      const formulation = await api.createFormulation({
        recipe_id: recipeId,
        format,
        target_trigger_food_ids: targets,
        application_food_ids: applications,
        dwell_profile: null,
        enzymes,
        serving_size_g: servingSize === '' ? null : Number(servingSize),
        measured_ph: measuredPh === '' ? null : Number(measuredPh),
        process_steps: steps,
        enzyme_addition_index: additionIndex,
      })
      const evaluation = await api.evaluate(formulation.id)
      navigate(`/evaluations/${evaluation.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Formulation setup</h1>
      {error && <p className="error" data-testid="setup-error">{error}</p>}

      <fieldset>
        <legend>Format</legend>
        {FORMATS.map((f) => (
          <label key={f.value}>
            <input type="radio" name="format" value={f.value} checked={format === f.value}
                   onChange={() => setFormat(f.value)} />
            {f.label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Trigger foods you want this to cover</legend>
        {triggerFoods.map((f) => (
          <label key={f.id}>
            <input type="checkbox" checked={targets.includes(f.id)}
                   data-testid={`trigger-${f.id}`}
                   onChange={() => toggle(targets, f.id, setTargets)} />
            {f.name}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Foods you will pour this on</legend>
        {applicationFoods.map((f) => (
          <label key={f.id}>
            <input type="checkbox" checked={applications.includes(f.id)}
                   onChange={() => toggle(applications, f.id, setApplications)} />
            {f.name}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Enzymes — proposed from your trigger foods, yours to change</legend>
        <p className="blurb">
          Removing one does not remove the finding: the tool still reports the
          substrate it leaves uncovered.
        </p>
        <table>
          <thead><tr><th>Enzyme</th><th>Dose</th><th>Phase</th><th>Encapsulated</th><th /></tr></thead>
          <tbody>
            {enzymes.map((selected, index) => {
              const enzyme = enzymeById.get(selected.enzyme_id)
              const update = (patch: Partial<SelectedEnzyme>) => {
                const next = [...enzymes]
                next[index] = { ...selected, ...patch }
                setEnzymes(next)
              }
              return (
                <tr key={selected.enzyme_id}>
                  <td>{enzyme?.name ?? selected.enzyme_id}</td>
                  <td>
                    <input type="number" min={0} value={selected.dose ?? ''}
                           data-testid={`dose-${selected.enzyme_id}`}
                           onChange={(e) =>
                             update({ dose: e.target.value === '' ? null : Number(e.target.value) })}
                    /> {enzyme?.dose_unit}
                  </td>
                  <td>
                    <select value={selected.phase}
                            onChange={(e) => update({ phase: e.target.value as 'wet' | 'dry' })}>
                      <option value="wet">wet</option>
                      <option value="dry">dry</option>
                    </select>
                  </td>
                  <td>
                    <input type="checkbox" checked={selected.encapsulated}
                           onChange={(e) => update({ encapsulated: e.target.checked })} />
                  </td>
                  <td>
                    <button type="button"
                            onClick={() => setEnzymes(enzymes.filter((x) => x !== selected))}>
                      Remove
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <select defaultValue="" data-testid="add-enzyme"
                onChange={(e) => {
                  const id = e.target.value
                  if (id && !enzymes.some((x) => x.enzyme_id === id)) {
                    setEnzymes([...enzymes, {
                      enzyme_id: id, dose: null,
                      phase: format === 'premixed_wet' || format === 'encapsulated_in_wet' ? 'wet' : 'dry',
                      encapsulated: false, source_choice: '',
                    }])
                  }
                  e.currentTarget.value = ''
                }}>
          <option value="" disabled>Add an enzyme…</option>
          {enzymeCatalog.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </fieldset>

      <fieldset>
        <legend>Serving and measured pH</legend>
        <label>Serving size (g)
          <input type="number" min={0} value={servingSize}
                 onChange={(e) => setServingSize(e.target.value)} />
        </label>
        <label>Measured pH — leave blank if you have not measured it
          <input type="number" step="0.1" min={0} max={14} value={measuredPh}
                 data-testid="measured-ph"
                 onChange={(e) => setMeasuredPh(e.target.value)} />
        </label>
      </fieldset>

      <fieldset>
        <legend>How you make it</legend>
        <table>
          <thead><tr><th>#</th><th>Step</th><th>Involves heat</th><th>Enzyme goes in after</th></tr></thead>
          <tbody>
            {steps.map((step, index) => (
              <tr key={step.order}>
                <td>{step.order}</td>
                <td>
                  <input value={step.label} onChange={(e) => {
                    const next = [...steps]
                    next[index] = { ...step, label: e.target.value }
                    setSteps(next)
                  }} />
                </td>
                <td>
                  <input type="checkbox" checked={step.is_heat}
                         data-testid={`heat-${step.order}`}
                         onChange={(e) => {
                           const next = [...steps]
                           next[index] = { ...step, is_heat: e.target.checked }
                           setSteps(next)
                         }} />
                </td>
                <td>
                  <input type="radio" name="addition" checked={additionIndex === step.order}
                         onChange={() => setAdditionIndex(step.order)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" onClick={() =>
          setSteps([...steps, { order: steps.length + 1, label: '', is_heat: false }])}>
          Add a step
        </button>
      </fieldset>

      <button type="button" onClick={evaluate} disabled={busy} data-testid="run-evaluation">
        {busy ? 'Running…' : 'Run the checks'}
      </button>
    </>
  )
}
