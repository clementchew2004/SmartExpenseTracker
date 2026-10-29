import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ExpenseFilters, ExpenseUpdate } from './client'
import {
  createExpense,
  createRepeat,
  deleteRepeat,
  listDueReminders,
  listRepeats,
  saveReminder,
  skipReminder,
  updateRepeat,
  deleteExpense,
  deleteDefaultBudget,
  getBudgets,
  getExpense,
  getMe,
  getMonthlyStats,
  listExpenses,
  parseText,
  setDefaultBudget,
  setMonthBudget,
  updateExpense,
} from './client'
import type { Currency, ExpenseCreate, RepeatUpdate } from './client'

/** This month's totals per currency and category (server state, cached by TanStack Query). */
export function useMonthlyStats(month: string) {
  return useQuery({
    queryKey: ['stats', 'monthly', month],
    queryFn: () => getMonthlyStats(month),
  })
}

/** Expenses for a date range (and optional category), newest first. */
export function useExpenses(filters: ExpenseFilters) {
  return useQuery({
    queryKey: ['expenses', filters],
    queryFn: () => listExpenses(filters),
  })
}

export function useExpense(id: number) {
  return useQuery({
    queryKey: ['expenses', 'one', id],
    queryFn: () => getExpense(id),
  })
}

/** The logged-in user (email, default currency). */
export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: getMe })
}

/** Sentence -> parsed expenses. Saves nothing. */
export function useParseText() {
  return useMutation({ mutationFn: parseText })
}

/** After any change, refetch everything built from expenses: the list and the chart. */
function useRefreshAfterChange() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['expenses'] }),
      queryClient.invalidateQueries({ queryKey: ['stats'] }),
      // "Spent" in the budget comes from expenses too, so the bar moves on save.
      queryClient.invalidateQueries({ queryKey: ['budgets'] }),
    ])
}

/** Save one confirmed expense. */
export function useCreateExpense() {
  const refresh = useRefreshAfterChange()
  return useMutation({ mutationFn: createExpense, onSuccess: refresh })
}

export function useUpdateExpense() {
  const refresh = useRefreshAfterChange()
  return useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: ExpenseUpdate }) =>
      updateExpense(id, changes),
    onSuccess: refresh,
  })
}

export function useDeleteExpense() {
  const refresh = useRefreshAfterChange()
  return useMutation({ mutationFn: deleteExpense, onSuccess: refresh })
}

/** A month's budgets per currency, with spent and the outlook (all computed by the API). */
export function useBudgets(month: string) {
  return useQuery({
    queryKey: ['budgets', month],
    queryFn: () => getBudgets(month),
  })
}

/** Any budget change: refetch every month, since a usual amount affects them all. */
function useRefreshBudgets() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ['budgets'] })
}

export function useSetDefaultBudget() {
  const refresh = useRefreshBudgets()
  return useMutation({
    mutationFn: ({ currency, amount }: { currency: Currency; amount: string }) =>
      setDefaultBudget(currency, amount),
    onSuccess: refresh,
  })
}

export function useDeleteDefaultBudget() {
  const refresh = useRefreshBudgets()
  return useMutation({ mutationFn: deleteDefaultBudget, onSuccess: refresh })
}

export function useSetMonthBudget() {
  const refresh = useRefreshBudgets()
  return useMutation({
    mutationFn: ({ month, currency, amount }: { month: string; currency: Currency; amount: string }) =>
      setMonthBudget(month, currency, amount),
    onSuccess: refresh,
  })
}

/** Repeats for Settings. */
export function useRepeats() {
  return useQuery({ queryKey: ['repeats', 'all'], queryFn: listRepeats })
}

/** Reminder cards for the Add page. */
export function useDueReminders() {
  return useQuery({ queryKey: ['repeats', 'due'], queryFn: listDueReminders })
}

function useRefreshRepeats() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ['repeats'] })
}

export function useCreateRepeat() {
  const refresh = useRefreshRepeats()
  return useMutation({ mutationFn: createRepeat, onSuccess: refresh })
}

/** Saving a reminder adds an expense, so the list, chart and budget refresh too. */
export function useSaveReminder() {
  const refreshExpenses = useRefreshAfterChange()
  const refreshRepeats = useRefreshRepeats()
  return useMutation({
    mutationFn: ({
      repeatId,
      dueDate,
      expense,
    }: {
      repeatId: number
      dueDate: string
      expense: ExpenseCreate
    }) => saveReminder(repeatId, dueDate, expense),
    onSuccess: () => Promise.all([refreshExpenses(), refreshRepeats()]),
  })
}

export function useSkipReminder() {
  const refresh = useRefreshRepeats()
  return useMutation({
    mutationFn: ({ repeatId, dueDate }: { repeatId: number; dueDate: string }) =>
      skipReminder(repeatId, dueDate),
    onSuccess: refresh,
  })
}

export function useUpdateRepeat() {
  const refresh = useRefreshRepeats()
  return useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: RepeatUpdate }) =>
      updateRepeat(id, changes),
    onSuccess: refresh,
  })
}

export function useDeleteRepeat() {
  const refresh = useRefreshRepeats()
  return useMutation({ mutationFn: deleteRepeat, onSuccess: refresh })
}
