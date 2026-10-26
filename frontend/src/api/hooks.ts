import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ExpenseFilters, ExpenseUpdate } from './client'
import {
  createExpense,
  deleteExpense,
  getExpense,
  getMonthlyStats,
  listExpenses,
  parseText,
  updateExpense,
} from './client'

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
