import { useEffect, useRef, useState } from 'react'

import type { ExpenseRead } from './api/client'
import { useDeleteExpense } from './api/hooks'

const UNDO_MS = 5000

/**
 * Delete with a real Undo: the expense is hidden straight away, but the DELETE request
 * is only sent after the Undo window. Undo just cancels the timer, so nothing is lost or
 * re-created. If the app closes inside the window, the expense simply isn't deleted.
 */
export function useDelayedDelete() {
  const [pending, setPending] = useState<ExpenseRead | null>(null)
  const timer = useRef<number | null>(null)
  const pendingRef = useRef<ExpenseRead | null>(null)
  const remove = useDeleteExpense()

  function commit() {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
    const expense = pendingRef.current
    pendingRef.current = null
    setPending(null)
    if (expense) remove.mutate(expense.id)
  }

  function schedule(expense: ExpenseRead) {
    // A second delete inside the window: finish the first one now.
    if (pendingRef.current) commit()
    pendingRef.current = expense
    setPending(expense)
    timer.current = window.setTimeout(commit, UNDO_MS)
  }

  function undo() {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
    pendingRef.current = null
    setPending(null)
  }

  // Leaving the app entirely (tab closed) cancels the timer: fail safe, nothing deleted.
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
  }, [])

  return { pending, schedule, undo, error: remove.error }
}
