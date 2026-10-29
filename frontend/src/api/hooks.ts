import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ExpenseFilters, ExpenseUpdate } from './client'
import {
  createExpense,
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
import type { Currency } from './client'

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
