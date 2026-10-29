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
export type UserRead = Schemas['UserRead']
export type RegisterRequest = Schemas['RegisterRequest']
type TokenResponse = Schemas['TokenResponse']
export type MonthBudgets = Schemas['MonthBudgets']
export type BudgetStatus = Schemas['BudgetStatus']
export type Outlook = BudgetStatus['outlook']
export type RepeatRead = Schemas['RepeatRead']
export type RepeatCreate = Schemas['RepeatCreate']
export type RepeatUpdate = Schemas['RepeatUpdate']
export type DueReminder = Schemas['DueReminder']
export type Frequency = RepeatRead['frequency']

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

// --- The access token ("wristband") --------------------------------------------

// A plain variable, not React state: request() isn't a component, and a reload
// should forget it. The httpOnly refresh cookie is what survives a reload.
let accessToken: string | null = null

// The app (auth.tsx) registers this to switch to the login screen when the
// session turns out to be over in the middle of using the app.
let onSessionEnded: () => void = () => {}
export function setOnSessionEnded(callback: () => void) {
  onSessionEnded = callback
}

// The one refresh in progress, if any. Every 401 that arrives meanwhile waits
// for this same trip instead of starting its own: two refreshes with the same
// cookie would look like a stolen token and log you out everywhere.
let refreshing: Promise<boolean> | null = null

/** Swap the refresh cookie for a new access token. True if still logged in. */
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const tokens = await request<TokenResponse>('/auth/refresh', { method: 'POST' })
      accessToken = tokens.access_token
      return true
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        accessToken = null
        return false
      }
      throw error // offline or server down: unknown, not "logged out"
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

// --- Sending requests ------------------------------------------------------------

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  form?: URLSearchParams // login is an OAuth2 form, not JSON
}

// A 401 from these means "wrong password" or "session over", never "token
// expired", so refreshing and retrying would only loop.
const NO_RETRY = new Set(['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'])

async function send(path: string, { method = 'GET', body, form }: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  try {
    return await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: form ?? (body === undefined ? undefined : JSON.stringify(body)),
      // Lets the browser send and store the refresh cookie on this other origin.
      credentials: 'include',
    })
  } catch {
    // fetch only throws when there is no response at all (server down, offline, CORS).
    throw new ApiError(0, "Can't reach the server - is the API running?")
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options)

  // Access token expired: get a new one, then try this request once more.
  if (response.status === 401 && !NO_RETRY.has(path)) {
    if (await refreshAccessToken()) {
      response = await send(path, options)
    } else {
      onSessionEnded() // the 30 days are over, or you logged out elsewhere
    }
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

// --- Accounts ----------------------------------------------------------------------

export async function login(email: string, password: string): Promise<void> {
  // OAuth2 password flow: the email goes in a field called "username".
  const form = new URLSearchParams({ username: email, password })
  const tokens = await request<TokenResponse>('/auth/login', { method: 'POST', form })
  accessToken = tokens.access_token
}

export function register(details: RegisterRequest): Promise<UserRead> {
  return request('/auth/register', { method: 'POST', body: details })
}

export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST' }) // revokes the cookie on the server
  } finally {
    accessToken = null // forget the token even if the server couldn't be reached
  }
}

export function getMe(): Promise<UserRead> {
  return request('/auth/me')
}

// --- Budgets -----------------------------------------------------------------------

export function getBudgets(month: string): Promise<MonthBudgets> {
  return request(`/budgets?month=${encodeURIComponent(month)}`)
}

/** Your usual monthly budget in this currency. */
export function setDefaultBudget(currency: Currency, amount: string): Promise<void> {
  return request(`/budgets/default/${currency}`, { method: 'PUT', body: { amount } })
}

export function deleteDefaultBudget(currency: Currency): Promise<void> {
  return request(`/budgets/default/${currency}`, { method: 'DELETE' })
}

/** One month's own amount ("2026-11"); replaces the usual one for that month. */
export function setMonthBudget(month: string, currency: Currency, amount: string): Promise<void> {
  return request(`/budgets/${month}/${currency}`, { method: 'PUT', body: { amount } })
}

// --- Repeating expenses --------------------------------------------------------------

/** Start repeating an expense you've just saved (its date is the first one). */
export function createRepeat(repeat: RepeatCreate): Promise<RepeatRead> {
  return request('/repeats', { method: 'POST', body: repeat })
}

export function listRepeats(): Promise<RepeatRead[]> {
  return request('/repeats')
}

/** Reminder cards: dates due up to today, worked out by the API when asked. */
export function listDueReminders(): Promise<DueReminder[]> {
  return request('/repeats/due')
}

/** Confirm a reminder (possibly edited) as a real expense. */
export function saveReminder(
  repeatId: number,
  dueDate: string,
  expense: ExpenseCreate,
): Promise<ExpenseRead> {
  return request(`/repeats/${repeatId}/save`, {
    method: 'POST',
    body: { ...expense, due_date: dueDate },
  })
}

/** Didn't pay this one: move on without saving. */
export function skipReminder(repeatId: number, dueDate: string): Promise<void> {
  return request(`/repeats/${repeatId}/skip`, { method: 'POST', body: { due_date: dueDate } })
}

/** Change future reminders; saved expenses are never touched. */
export function updateRepeat(id: number, changes: RepeatUpdate): Promise<RepeatRead> {
  return request(`/repeats/${id}`, { method: 'PATCH', body: changes })
}

export function deleteRepeat(id: number): Promise<void> {
  return request(`/repeats/${id}`, { method: 'DELETE' })
}
