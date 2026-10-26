import type { components } from './types'

// Generated from the API's /openapi.json - rerun `npm run gen:api` after backend changes.
type Schemas = components['schemas']
export type ParsedExpense = Schemas['ParsedExpense']
export type ParseResult = Schemas['ParseResult']
export type ExpenseCreate = Schemas['ExpenseCreate']
export type ExpenseRead = Schemas['ExpenseRead']
export type ExpenseUpdate = Schemas['ExpenseUpdate']
export type MonthlyStats = Schemas['MonthlyStats']
export type Currency = ExpenseCreate['currency']
export type Category = ExpenseCreate['category']

const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** A failed API call, with a message that is safe to show the user. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type ValidationIssue = { loc: (string | number)[]; msg: string }

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    // Our own errors: HTTPException(detail="No amount found for 'Bus' ...")
    if (typeof body.detail === 'string') return body.detail
    // FastAPI's validation errors: a list of {loc, msg}
    if (Array.isArray(body.detail)) {
      return (body.detail as ValidationIssue[])
        .map((issue) => `${issue.loc.at(-1)}: ${issue.msg}`)
        .join('; ')
    }
  } catch {
    // The body wasn't JSON; fall through to a generic message.
  }
  return `Something went wrong (${response.status})`
}

type RequestOptions = { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown }

async function request<T>(path: string, { method = 'GET', body }: RequestOptions = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    // fetch only throws when there is no response at all (server down, offline, CORS).
    throw new ApiError(0, "Can't reach the server - is the API running?")
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  // 204 No Content (e.g. DELETE) has no body to parse.
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function parseText(text: string): Promise<ParseResult> {
  return request('/parse/text', { method: 'POST', body: { text } })
}

export function createExpense(expense: ExpenseCreate): Promise<ExpenseRead> {
  return request('/expenses', { method: 'POST', body: expense })
}

export type ExpenseFilters = { from: string; to: string; category?: Category; limit?: number }

export function listExpenses({ from, to, category, limit = 200 }: ExpenseFilters): Promise<ExpenseRead[]> {
  const params = new URLSearchParams({ from, to, limit: String(limit) })
  if (category) params.set('category', category)
  return request(`/expenses?${params}`)
}

export function getExpense(id: number): Promise<ExpenseRead> {
  return request(`/expenses/${id}`)
}

export function updateExpense(id: number, changes: ExpenseUpdate): Promise<ExpenseRead> {
  return request(`/expenses/${id}`, { method: 'PATCH', body: changes })
}

export function deleteExpense(id: number): Promise<void> {
  return request(`/expenses/${id}`, { method: 'DELETE' })
}

export function getMonthlyStats(month: string): Promise<MonthlyStats> {
  return request(`/stats/monthly?month=${encodeURIComponent(month)}`)
}
