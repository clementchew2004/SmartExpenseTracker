import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import type { DueReminder, ExpenseCreate } from '../api/client'
import { ApiError } from '../api/client'
import { useDueReminders, useSaveReminder, useSkipReminder } from '../api/hooks'
import { formatMoney } from '../api/options'
import { dayLabel } from '../dates'
import { ExpenseFields } from './ExpenseFields'

/** Due repeats as filled-in cards you confirm: never saved without you. */
export function Reminders() {
  const due = useDueReminders()

  if (!due.data || due.data.length === 0) return null

  // The API only accepts the oldest date of each repeat first, so later
  // cards of the same repeat wait for it.
  const firstOf = new Map<number, string>()
  for (const r of due.data) {
    if (!firstOf.has(r.repeat_id)) firstOf.set(r.repeat_id, r.due_date)
  }

  return (
    <section className="reminders" aria-label="Reminders">
      <h2>Reminders ({due.data.length})</h2>
      {due.data.map((r) => (
        <ReminderCard
          key={`${r.repeat_id}-${r.due_date}`}
          reminder={r}
          waitingFor={firstOf.get(r.repeat_id) === r.due_date ? null : firstOf.get(r.repeat_id)!}
        />
      ))}
    </section>
  )
}

function ReminderCard({ reminder, waitingFor }: { reminder: DueReminder; waitingFor: string | null }) {
  // The card's own copy, so you can change this month's amount before saving.
  const [draft, setDraft] = useState<ExpenseCreate>({
    amount: reminder.amount,
    currency: reminder.currency,
    date: reminder.due_date,
    merchant: reminder.merchant,
    category: reminder.category,
    note: reminder.note ?? null,
  })
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const save = useSaveReminder()
  const skip = useSkipReminder()
  const queryClient = useQueryClient()
  const busy = save.isPending || skip.isPending
  const ids = { repeatId: reminder.repeat_id, dueDate: reminder.due_date }

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
    } catch (e) {
      // 409: already saved or skipped elsewhere (e.g. on your phone) - refresh the list.
      if (e instanceof ApiError && e.status === 409) {
        void queryClient.invalidateQueries({ queryKey: ['repeats'] })
      }
      setError(
        e instanceof ApiError && e.status === 409
          ? 'Already dealt with - refreshing'
          : e instanceof Error
            ? e.message
            : 'Something went wrong',
      )
    }
  }

  return (
    <article
      className="card reminder"
      aria-label={`Reminder: ${reminder.merchant}, due ${dayLabel(reminder.due_date)}`}
    >
      <p className="reminder-due">
        <svg className="reminder-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 12a8 8 0 0 1 13.7-5.6L20 9M20 4v5h-5M20 12a8 8 0 0 1-13.7 5.6L4 15M4 20v-5h5" />
        </svg>
        <span className="due-pill">Due {dayLabel(reminder.due_date)}</span>
      </p>
      {editing ? (
        <ExpenseFields
          expense={draft}
          onChange={(field, value) => setDraft((d) => ({ ...d, [field]: value }))}
        />
      ) : (
        <p className="reminder-summary">
          <strong>{draft.merchant}</strong>
          <span>{formatMoney(String(draft.amount), draft.currency)}</span>
        </p>
      )}

      {waitingFor && <p className="hint">Deal with the {dayLabel(waitingFor)} one first</p>}
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
          onClick={() => setEditing((e) => !e)}
        >
          {editing ? 'Done' : 'Edit'}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy || waitingFor !== null}
          onClick={() => run(() => skip.mutateAsync(ids))}
        >
          Skip
        </button>
        <button
          type="button"
          disabled={busy || waitingFor !== null}
          onClick={() => run(() => save.mutateAsync({ ...ids, expense: draft }))}
        >
          {save.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </article>
  )
}
