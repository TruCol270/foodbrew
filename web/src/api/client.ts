import type {
  AuditEvent, Comparison, Enzyme, Evaluation, EvaluationSummary, Food, Formulation,
  Proposal, Recipe, SelectedEnzyme, Substrate, SubstrateRow, SymptomDose, Trial, TrialSummary,
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

const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })

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

  applyVariant: (evaluationId: string, suggestionId: number) =>
    post<Evaluation>(`/evaluations/${evaluationId}/apply-variant`, { suggestion_id: suggestionId }),

  compare: (ids: string[]) => {
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('ids', id))
    return request<Comparison>(`/compare?${params}`)
  },

  updateEnzyme: (id: string, fields: Record<string, unknown>) =>
    put<Enzyme>(`/enzymes/${id}`, { fields }),
  resetEnzyme: (id: string) => post<Enzyme>(`/enzymes/${id}/reset`),
  updateFood: (id: string, fields: Record<string, unknown>) =>
    put<Food>(`/foods/${id}`, { fields }),
  resetFood: (id: string) => post<Food>(`/foods/${id}/reset`),

  proposals: (status?: Proposal['status']) =>
    request<Proposal[]>(`/proposals${status ? `?status=${status}` : ''}`),
  createProposal: (body: unknown) => post<Proposal>('/proposals', body),
  approveProposal: (id: string) => post<Proposal>(`/proposals/${id}/approve`),
  rejectProposal: (id: string) => post<Proposal>(`/proposals/${id}/reject`),

  auditFeed: () => request<AuditEvent[]>('/audit'),

  startTrial: (evaluationId: string) => post<Trial>(`/evaluations/${evaluationId}/trial`),
  trial: (id: string) => request<Trial>(`/trials/${id}`),
  activeTrials: () => request<TrialSummary[]>('/trials'),
  trialsForEvaluation: (evaluationId: string) =>
    request<TrialSummary[]>(`/evaluations/${evaluationId}/trials`),
  setTrialStatus: (id: string, status: 'complete' | 'abandoned') =>
    post<Trial>(`/trials/${id}/status`, { status }),

  addBatch: (trialId: string, body: unknown) => post<Trial>(`/trials/${trialId}/batches`, body),
  addObservation: (batchId: string, body: unknown) =>
    post<Trial>(`/trial-batches/${batchId}/observations`, body),
  addSymptomEntry: (batchId: string, body: unknown) =>
    post<Trial>(`/trial-batches/${batchId}/symptom-entries`, body),
  previewSymptom: (batchId: string, body: unknown) =>
    post<SymptomDose>(`/trial-batches/${batchId}/symptom-preview`, body),

  reportUrl: (evaluationId: string) => `/api/v1/export/${evaluationId}.md`,
}
