import type { Category, Currency, ExpenseCreate } from '../api/client'
import { CATEGORIES, CURRENCIES } from '../api/options'

type Props = {
  expense: ExpenseCreate
  onChange: <K extends keyof ExpenseCreate>(field: K, value: ExpenseCreate[K]) => void
}

/** The five editable fields, shared by the confirmation card and the edit page. */
export function ExpenseFields({ expense, onChange }: Props) {
  return (
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
        <input type="date" value={expense.date} onChange={(e) => onChange('date', e.target.value)} />
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
  )
}
