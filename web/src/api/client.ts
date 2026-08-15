import type {
  Enzyme, Evaluation, EvaluationSummary, Food, Formulation, Recipe,
  SelectedEnzyme, Substrate, SubstrateRow,
} from './types'

/** The API's error shape. A rejected formulation is normal traffic, not a crash. */
export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      // FastAPI reports schema errors as a list; ours are a plain string.
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status line */
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  enzymes: () => request<Enzyme[]>('/enzymes'),
  substrates: () => request<Substrate[]>('/substrates'),
  foods: (role?: 'recipe_ingredient' | 'trigger' | 'application') =>
    request<Food[]>(`/foods${role ? `?role=${role}` : ''}`),
  createFood: (body: unknown) => post<Food>('/foods', body),

  recipes: () => request<Recipe[]>('/recipes'),
  recipe: (id: string) => request<Recipe>(`/recipes/${id}`),
  createRecipe: (body: unknown) => post<Recipe>('/recipes', body),
  updateRecipe: (id: string, body: unknown) =>
    request<Recipe>(`/recipes/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  substrateSummary: (id: string) => request<SubstrateRow[]>(`/recipes/${id}/substrate-summary`),

  createFormulation: (body: unknown) => post<Formulation>('/formulations', body),
  formulation: (id: string) => request<Formulation>(`/formulations/${id}`),
  proposedEnzymes: (triggerFoodIds: string[], format: string) => {
    const params = new URLSearchParams({ format })
    triggerFoodIds.forEach((id) => params.append('trigger_food_ids', id))
    return request<SelectedEnzyme[]>(`/proposed-enzymes?${params}`)
  },

  evaluate: (formulationId: string) =>
    post<Evaluation>(`/formulations/${formulationId}/evaluate`),
  evaluation: (id: string) => request<Evaluation>(`/evaluations/${id}`),
  recentEvaluations: () => request<EvaluationSummary[]>('/evaluations'),
}
