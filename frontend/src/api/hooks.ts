import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createExpense, getMonthlyStats, parseText } from './client'

/** This month's totals per currency and category (server state, cached by TanStack Query). */
export function useMonthlyStats(month: string) {
  return useQuery({
    queryKey: ['stats', 'monthly', month],
    queryFn: () => getMonthlyStats(month),
  })
}

/** Sentence -> parsed expenses. Saves nothing. */
export function useParseText() {
  return useMutation({ mutationFn: parseText })
}

/** Save one confirmed expense, then refresh anything showing stats. */
export function useCreateExpense() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createExpense,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stats'] }),
  })
}
