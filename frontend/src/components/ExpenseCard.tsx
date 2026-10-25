import { useState } from 'react'

import type { Category, Currency, ExpenseCreate } from '../api/client'
import { useCreateExpense } from '../api/hooks'
import { CATEGORIES, CURRENCIES, formatMoney } from '../api/options'

type Props = {
  expense: ExpenseCreate
  onSaved: () => void
  onDiscard: () => void
}

/** One parsed expense to review: view it, edit it, then save or discard. Nothing is saved until Save. */
export function ExpenseCard({ expense, onSaved, onDiscard }: Props) {
  const [draft, setDraft] = useState<ExpenseCreate>(expense)
  const [editing, setEditing] = useState(false)
  const save = useCreateExpense()
  const otherCurrency: Currency = draft.currency === 'GBP' ? 'MYR' : 'GBP'

  function update<K extends keyof ExpenseCreate>(field: K, value: ExpenseCreate[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  function handleSave() {
    save.mutate(draft, {
      onSuccess: onSaved,
      // Let the user fix it straight away: errors keep the card open for editing.
      onError: () => setEditing(true),
    })
  }

  return (
    <article className="card" aria-label={`Expense: ${draft.merchant}`}>
      {editing ? (
        <div className="card-fields">
          <label>
            Amount
            <input
              inputMode="decimal"
              value={String(draft.amount)}
              onChange={(e) => update('amount', e.target.value)}
            />
          </label>
          <label>
            Currency
            <select
              value={draft.currency}
              onChange={(e) => update('currency', e.target.value as Currency)}
            >
              {CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            Date
            <input type="date" value={draft.date} onChange={(e) => update('date', e.target.value)} />
          </label>
          <label>
            Merchant
            <input value={draft.merchant} onChange={(e) => update('merchant', e.target.value)} />
          </label>
          <label>
            Category
            <select
              value={draft.category}
              onChange={(e) => update('category', e.target.value as Category)}
            >
              {CATEGORIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
      ) : (
        <dl className="card-summary">
          <div className="card-amount">
            <dt>Amount</dt>
            <dd>
              {formatMoney(String(draft.amount), draft.currency)}
              {/* Currency is the field most likely to be wrong, so fixing it is one tap. */}
              <button
                type="button"
                className="currency-chip"
                aria-label={`Currency ${draft.currency}. Switch to ${otherCurrency}`}
                onClick={() => update('currency', otherCurrency)}
              >
                {draft.currency} ⇄
              </button>
            </dd>
          </div>
          <div>
            <dt>Merchant</dt>
            <dd>{draft.merchant}</dd>
          </div>
          <div>
            <dt>Category</dt>
            <dd>{draft.category}</dd>
          </div>
          <div>
            <dt>Date</dt>
            <dd>{draft.date}</dd>
          </div>
        </dl>
      )}

      {save.isError && (
        <p className="error" role="alert">
          {save.error.message}
        </p>
      )}

      <div className="card-actions">
        <button type="button" className="secondary" onClick={() => setEditing(!editing)}>
          {editing ? 'Done' : 'Edit'}
        </button>
        <button type="button" className="secondary" onClick={onDiscard}>
          Discard
        </button>
        <button type="button" onClick={handleSave} disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </article>
  )
}
