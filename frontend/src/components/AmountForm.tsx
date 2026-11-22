import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import type { Currency } from '../api/client'
import { CURRENCY_SYMBOL } from '../api/options'

/** An amount box with Save (and optional Cancel). The server checks the amount.
 * Used by the budget cards on Insights and the usual amounts in Settings. */
export function AmountForm({
  currency,
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  currency: Currency
  initial: string
  submitLabel: string
  onSubmit: (amount: string) => Promise<unknown>
  onCancel?: () => void
}) {
  const [amount, setAmount] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const inputId = useId() // unique even when two GBP forms are open at once

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSubmit(amount.trim())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="amount-form" onSubmit={handleSubmit}>
      <div className="input-row">
        <label className="visually-hidden" htmlFor={inputId}>
          Amount in {currency}
        </label>
        <span className="amount-symbol" aria-hidden="true">
          {CURRENCY_SYMBOL[currency]}
        </span>
        <input
          id={inputId}
          inputMode="decimal"
          required
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <button type="submit" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
      {onCancel && (
        <button type="button" className="secondary small" onClick={onCancel}>
          Cancel
        </button>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
