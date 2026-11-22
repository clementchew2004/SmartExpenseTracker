import { useState } from 'react'

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

  if (budgets.isPending) return <p className="muted">Loading…</p>
  if (budgets.isError) return <p className="error">{budgets.error.message}</p>
  const defaults = budgets.data.defaults

  return (
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
                <span className="usual-actions">
                  {amount && (
                    <button
                      type="button"
                      className="secondary small"
                      onClick={() => remove.mutate(currency)}
                    >
                      Remove
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary small"
                    onClick={() => setEditing(currency)}
                  >
                    {amount ? 'Edit' : 'Set'}
                  </button>
                </span>
              </>
            )}
          </li>
        )
      })}
    </ul>
  )
}
