import type { components } from './types'

// Generated from the API's /openapi.json - rerun `npm run gen:api` after backend changes.
type Schemas = components['schemas']
export type ParsedExpense = Schemas['ParsedExpense']
export type ParseResult = Schemas['ParseResult']
export type ExpenseCreate = Schemas['ExpenseCreate']
export type ExpenseRead = Schemas['ExpenseRead']
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

async function request<T>(path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
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
  return (await response.json()) as T
}

export function parseText(text: string): Promise<ParseResult> {
  return request('/parse/text', { text })
}

export function createExpense(expense: ExpenseCreate): Promise<ExpenseRead> {
  return request('/expenses', expense)
}

export function getMonthlyStats(month: string): Promise<MonthlyStats> {
  return request(`/stats/monthly?month=${encodeURIComponent(month)}`)
}
