import type { Category, Currency, ExpenseCreate } from '../api/client'
import { CATEGORIES, CURRENCIES, formatMoney } from '../api/options'

type Props = {
  expense: ExpenseCreate
  editing: boolean
  saving: boolean
  error: string | null
  onToggleEdit: () => void
  onChange: <K extends keyof ExpenseCreate>(field: K, value: ExpenseCreate[K]) => void
  onSave: () => void
  onDiscard: () => void
}

/**
 * One parsed expense to review. Controlled: the values live in QuickAdd (so "Save all"
 * can see your edits); this card only shows them and reports changes.
 */
export function ExpenseCard({
  expense,
  editing,
  saving,
  error,
  onToggleEdit,
  onChange,
  onSave,
  onDiscard,
}: Props) {
  const otherCurrency: Currency = expense.currency === 'GBP' ? 'MYR' : 'GBP'

  return (
    <article className="card" aria-label={`Expense: ${expense.merchant}`}>
      {editing ? (
        <div className="card-fields">
          <label>
            Amount
            <input
              inputMode="decimal"
              value={String(expense.amount)}
              onChange={(e) => onChange('amount', e.target.value)}
            />
          </label>
          <label>
            Currency
            <select
              value={expense.currency}
              onChange={(e) => onChange('currency', e.target.value as Currency)}
            >
              {CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            Date
            <input
              type="date"
              value={expense.date}
              onChange={(e) => onChange('date', e.target.value)}
            />
          </label>
          <label>
            Merchant
            <input value={expense.merchant} onChange={(e) => onChange('merchant', e.target.value)} />
          </label>
          <label>
            Category
            <select
              value={expense.category}
              onChange={(e) => onChange('category', e.target.value as Category)}
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
              {formatMoney(String(expense.amount), expense.currency)}
              {/* Currency is the field most likely to be wrong, so fixing it is one tap. */}
              <button
                type="button"
                className="currency-chip"
                aria-label={`Currency ${expense.currency}. Switch to ${otherCurrency}`}
                onClick={() => onChange('currency', otherCurrency)}
              >
                {expense.currency} ⇄
              </button>
            </dd>
          </div>
          <div>
            <dt>Merchant</dt>
            <dd>{expense.merchant}</dd>
          </div>
          <div>
            <dt>Category</dt>
            <dd>{expense.category}</dd>
          </div>
          <div>
            <dt>Date</dt>
            <dd>{expense.date}</dd>
          </div>
        </dl>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <div className="card-actions">
        <button type="button" className="secondary" onClick={onToggleEdit}>
          {editing ? 'Done' : 'Edit'}
        </button>
        <button type="button" className="secondary" onClick={onDiscard}>
          Discard
        </button>
        <button type="button" onClick={onSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </article>
  )
}
