import { useEffect, useState } from 'react'

import type { Currency } from '../api/client'
import { useBudgets, useDeleteDefaultBudget, useSetDefaultBudget } from '../api/hooks'
import { CURRENCIES, formatMoney } from '../api/options'
import { monthKey } from '../dates'
import { AmountForm } from './AmountForm'

/** Your usual amounts, used for any month you don't set yourself. A set-once
 * preference, so it lives in Settings; Insights only shows the month. */
export function UsualBudgets() {
  // The usual amounts come with any month's budgets; this month's is already cached
  // if you've been on Insights.
  const [thisMonth] = useState(() => monthKey(new Date()))
  const budgets = useBudgets(thisMonth)
  const [editing, setEditing] = useState<Currency | null>(null)
  const setDefault = useSetDefaultBudget()
  const remove = useDeleteDefaultBudget()
  // The last amount removed, so Undo can put it back (like deleting an expense).
  const [removed, setRemoved] = useState<{ currency: Currency; amount: string } | null>(null)

  // Offer Undo for a few seconds, then let it go.
  useEffect(() => {
    if (!removed) return
    const timer = setTimeout(() => setRemoved(null), 6000)
    return () => clearTimeout(timer)
  }, [removed])

  if (budgets.isPending) return <p className="muted">Loading…</p>
  if (budgets.isError) return <p className="error">{budgets.error.message}</p>
  const defaults = budgets.data.defaults

  function handleRemove(currency: Currency, amount: string) {
    remove.mutate(currency, { onSuccess: () => setRemoved({ currency, amount }) })
  }

  function undoRemove() {
    if (!removed) return
    setDefault.mutate(removed, { onSuccess: () => setRemoved(null) })
  }

  return (
    <>
      {removed && (
        <div className="notice" role="status">
          <span>
            Removed your usual {removed.currency} budget (
            {formatMoney(removed.amount, removed.currency)})
          </span>
          <button type="button" className="secondary small" onClick={undoRemove}>
            Undo
          </button>
        </div>
      )}
      <ul className="usual-budgets">
        {CURRENCIES.map((currency) => {
          const amount = defaults[currency]
          return (
            <li key={currency}>
              {editing === currency ? (
                <AmountForm
                  currency={currency}
                  initial={amount ?? ''}
                  submitLabel="Save"
                  onCancel={() => setEditing(null)}
                  onSubmit={async (value) => {
                    await setDefault.mutateAsync({ currency, amount: value })
                    setEditing(null)
                  }}
                />
              ) : (
                <>
                  <span>
                    {currency}{' '}
                    {amount ? (
                      <strong>{formatMoney(amount, currency)}</strong>
                    ) : (
                      <span className="muted">not set</span>
                    )}
                  </span>
                  {/* Edit first, then the destructive action: the same order as every row. */}
                  <span className="row-actions">
                    <button
                      type="button"
                      className="secondary small"
                      onClick={() => setEditing(currency)}
                    >
                      {amount ? 'Edit' : 'Set'}
                    </button>
                    {amount && (
                      <button
                        type="button"
                        className="secondary small"
                        disabled={remove.isPending}
                        onClick={() => handleRemove(currency, amount)}
                      >
                        Remove
                      </button>
                    )}
                  </span>
                </>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}
