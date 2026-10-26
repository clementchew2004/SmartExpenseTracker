import type { Currency, ExpenseCreate } from '../api/client'
import { formatMoney } from '../api/options'
import { ExpenseFields } from './ExpenseFields'

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
    <article
      className="card"
      aria-label={`Expense: ${expense.merchant}, ${formatMoney(String(expense.amount), expense.currency)}`}
    >
      {editing ? (
        <ExpenseFields expense={expense} onChange={onChange} />
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
        <button
          type="button"
          className="secondary"
          aria-expanded={editing}
          onClick={onToggleEdit}
        >
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
