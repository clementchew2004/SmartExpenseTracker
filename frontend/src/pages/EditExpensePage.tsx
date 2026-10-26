import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import type { ExpenseCreate, ExpenseRead, ExpenseUpdate } from '../api/client'
import { useExpense, useUpdateExpense } from '../api/hooks'
import { formatMoney } from '../api/options'
import { ExpenseFields } from '../components/ExpenseFields'

type Props = {
  /** Hide the expense now; really delete it after the Undo window. */
  onDelete: (expense: ExpenseRead) => void
}

/** One saved expense as an editable card: change fields, save, or delete. */
export function EditExpensePage({ onDelete }: Props) {
  const id = Number(useParams().id)
  const expense = useExpense(id)

  if (expense.isPending) return <p className="muted">Loading…</p>
  if (expense.isError) {
    return (
      <div className="card" role="alert">
        <p className="error">{expense.error.message}</p>
        <Link to="/expenses">Back to expenses</Link>
      </div>
    )
  }
  // key: a different expense gets a fresh form, so the form can copy the data into
  // its own state once on mount instead of syncing it with an effect.
  return <EditForm key={expense.data.id} expense={expense.data} onDelete={onDelete} />
}

function EditForm({ expense, onDelete }: { expense: ExpenseRead; onDelete: Props['onDelete'] }) {
  const { id, ...fields } = expense
  const [draft, setDraft] = useState<ExpenseCreate>({ ...fields, note: fields.note ?? null })
  const [confirming, setConfirming] = useState(false)
  const update = useUpdateExpense()
  const navigate = useNavigate()
  const listUrl = `/expenses?month=${expense.date.slice(0, 7)}`

  function change<K extends keyof ExpenseCreate>(field: K, value: ExpenseCreate[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  // PATCH only what changed - the API's partial update.
  const changes: ExpenseUpdate = {}
  for (const key of Object.keys(draft) as (keyof ExpenseCreate)[]) {
    if (String(draft[key] ?? '') !== String(expense[key] ?? '')) {
      Object.assign(changes, { [key]: draft[key] })
    }
  }
  const hasChanges = Object.keys(changes).length > 0

  function handleSave() {
    update.mutate({ id, changes }, { onSuccess: () => navigate(listUrl) })
  }

  function handleDelete() {
    onDelete(expense)
    navigate(listUrl)
  }

  const label = `${expense.merchant} ${formatMoney(expense.amount, expense.currency)}`

  return (
    <article className="card edit-card" aria-label={`Edit expense: ${label}`}>
      <div className="edit-header">
        <Link to={listUrl} className="back-link">
          ‹ Expenses
        </Link>
        <h1>Edit expense</h1>
      </div>

      <ExpenseFields expense={draft} onChange={change} />

      {update.isError && (
        <p className="error" role="alert">
          {update.error.message}
        </p>
      )}

      {confirming ? (
        <div className="confirm" role="alertdialog" aria-label="Confirm delete">
          <p>Delete {label}?</p>
          <div className="card-actions">
            <button type="button" className="secondary" onClick={() => setConfirming(false)}>
              Cancel
            </button>
            <button type="button" className="danger" onClick={handleDelete} autoFocus>
              Delete
            </button>
          </div>
        </div>
      ) : (
        <div className="card-actions">
          <button type="button" className="secondary" onClick={() => setConfirming(true)}>
            Delete
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!hasChanges || update.isPending}
          >
            {update.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      )}
    </article>
  )
}
