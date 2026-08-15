import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { TruthValue } from '../components/TruthValue'
import type { Food, Ingredient, SubstrateRow } from '../api/types'

interface CustomFoodDraft {
  name: string
  category: string
  ph: string
  water_content_pct: string
  contains_substrate_ids: string[]
}

const EMPTY_CUSTOM: CustomFoodDraft = {
  name: '', category: '', ph: '', water_content_pct: '', contains_substrate_ids: [],
}

export default function RecipeBuilder() {
  const { recipeId } = useParams()
  const navigate = useNavigate()

  const [foods, setFoods] = useState<Food[]>([])
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [ingredients, setIngredients] = useState<Ingredient[]>([])
  const [summary, setSummary] = useState<SubstrateRow[]>([])
  const [savedId, setSavedId] = useState<string | null>(recipeId ?? null)
  const [custom, setCustom] = useState<CustomFoodDraft | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { api.foods('recipe_ingredient').then(setFoods).catch((e) => setError(e.message)) }, [])

  useEffect(() => {
    if (!recipeId) return
    api.recipe(recipeId).then((r) => {
      setName(r.name); setNotes(r.notes); setIngredients(r.ingredients); setSavedId(r.id)
    }).catch((e) => setError(e.message))
  }, [recipeId])

  useEffect(() => {
    if (!savedId) return
    api.substrateSummary(savedId).then(setSummary).catch(() => setSummary([]))
  }, [savedId, ingredients])

  const byId = new Map(foods.map((f) => [f.id, f]))
  const total = ingredients.reduce((sum, i) => sum + (i.amount_g || 0), 0)

  function addIngredient(foodId: string) {
    if (!foodId || ingredients.some((i) => i.food_id === foodId)) return
    setIngredients([...ingredients, { food_id: foodId, amount_g: 0, order: ingredients.length + 1 }])
  }

  async function save() {
    setError(null)
    const body = { name, notes, ingredients }
    try {
      const saved = savedId
        ? await api.updateRecipe(savedId, body)
        : await api.createRecipe(body)
      setSavedId(saved.id)
      setSummary(await api.substrateSummary(saved.id))
    } catch (e) { setError((e as Error).message) }
  }

  async function saveCustomFood() {
    if (!custom) return
    setError(null)
    try {
      const created = await api.createFood({
        name: custom.name,
        category: custom.category,
        is_recipe_ingredient: true,
        ph: custom.ph === '' ? null : Number(custom.ph),
        water_content_pct:
          custom.water_content_pct === '' ? null : Number(custom.water_content_pct),
        contains_substrate_ids: custom.contains_substrate_ids,
      })
      setFoods([...foods, created])
      setCustom(null)
      addIngredient(created.id)
    } catch (e) { setError((e as Error).message) }
  }

  return (
    <>
      <h1>{savedId ? 'Edit recipe' : 'New recipe'}</h1>
      {error && <p className="error">{error}</p>}

      <label>Name
        <input value={name} onChange={(e) => setName(e.target.value)} data-testid="recipe-name" />
      </label>
      <label>Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>

      <fieldset>
        <legend>Ingredients</legend>
        <select
          defaultValue=""
          onChange={(e) => { addIngredient(e.target.value); e.currentTarget.value = '' }}
          data-testid="food-picker"
        >
          <option value="" disabled>Add an ingredient…</option>
          {foods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <button type="button" onClick={() => setCustom(EMPTY_CUSTOM)}>
          Add a food that isn't listed
        </button>

        <table>
          <thead>
            <tr><th>Food</th><th>Grams</th><th>pH</th><th>Water</th><th /></tr>
          </thead>
          <tbody>
            {ingredients.map((ing, index) => {
              const food = byId.get(ing.food_id)
              return (
                <tr key={ing.food_id}>
                  <td>{food?.name ?? ing.food_id}</td>
                  <td>
                    <input
                      type="number" min={0} value={ing.amount_g}
                      data-testid={`amount-${ing.food_id}`}
                      onChange={(e) => {
                        const next = [...ingredients]
                        next[index] = { ...ing, amount_g: Number(e.target.value) }
                        setIngredients(next)
                      }}
                    />
                  </td>
                  <td>{food && <TruthValue tracked={food.ph} />}</td>
                  <td>{food && <TruthValue tracked={food.water_content_pct} unit="%" />}</td>
                  <td>
                    <button type="button"
                            onClick={() => setIngredients(ingredients.filter((x) => x !== ing))}>
                      Remove
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p>Batch total: {total} g</p>
      </fieldset>

      {custom && (
        <fieldset>
          <legend>New food — everything you enter is stored as your own value</legend>
          <label>Name
            <input value={custom.name} onChange={(e) => setCustom({ ...custom, name: e.target.value })} />
          </label>
          <label>Category
            <input value={custom.category}
                   onChange={(e) => setCustom({ ...custom, category: e.target.value })} />
          </label>
          <label>pH (leave blank if you have not measured it)
            <input type="number" step="0.1" value={custom.ph}
                   onChange={(e) => setCustom({ ...custom, ph: e.target.value })} />
          </label>
          <label>Water content %
            <input type="number" step="1" value={custom.water_content_pct}
                   onChange={(e) => setCustom({ ...custom, water_content_pct: e.target.value })} />
          </label>
          <button type="button" onClick={saveCustomFood}>Save food</button>
          <button type="button" onClick={() => setCustom(null)}>Cancel</button>
        </fieldset>
      )}

      {summary.length > 0 && (
        <fieldset>
          <legend>This recipe itself contains</legend>
          <ul>
            {summary.map((row) => (
              <li key={row.substrate_id}>
                {row.substrate_name} ({row.from_food_names.join(', ')})
                {row.is_prebiotic && ' — this one is a prebiotic fibre'}
                {row.no_commercial_enzyme && ' — no commercial enzyme exists for this'}
              </li>
            ))}
          </ul>
        </fieldset>
      )}

      <button type="button" onClick={save} data-testid="save-recipe">Save recipe</button>
      {savedId && (
        <button type="button" data-testid="to-formulation"
                onClick={() => navigate(`/recipes/${savedId}/formulation`)}>
          Set up a formulation
        </button>
      )}
    </>
  )
}
