import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import type { ExpenseCreate } from '../api/client'
import { useParseText } from '../api/hooks'
import { ExpenseCard } from './ExpenseCard'

type Draft = { id: string; expense: ExpenseCreate }

/** The main screen's top half: sentence in, editable cards out. */
export function QuickAdd() {
  const [text, setText] = useState('')
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [savedMessage, setSavedMessage] = useState(false)
  const parse = useParseText()

  // Hide "Successfully added" after a few seconds.
  useEffect(() => {
    if (!savedMessage) return
    const timer = setTimeout(() => setSavedMessage(false), 3000)
    return () => clearTimeout(timer)
  }, [savedMessage])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!text.trim() || parse.isPending) return
    setSavedMessage(false)
    parse.mutate(text, {
      onSuccess: (result) =>
        setDrafts(
          result.expenses.map((parsed) => ({
            id: crypto.randomUUID(),
            // The API only returns parsed expenses that have an amount.
            expense: { ...parsed, amount: parsed.amount ?? '' },
          })),
        ),
    })
  }

  function remove(id: string, saved: boolean) {
    const remaining = drafts.filter((d) => d.id !== id)
    setDrafts(remaining)
    if (saved) setSavedMessage(true)
    // Every card dealt with: clear the box for the next expense.
    if (remaining.length === 0) setText('')
  }

  return (
    <section className="quick-add" aria-label="Add an expense">
      <form onSubmit={handleSubmit}>
        <label htmlFor="expense-text" className="visually-hidden">
          Describe what you spent
        </label>
        <div className="input-row">
          <input
            id="expense-text"
            autoFocus
            autoComplete="off"
            placeholder="4.50 bubble tea yesterday"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={500}
          />
          <button type="submit" disabled={!text.trim() || parse.isPending}>
            {parse.isPending ? 'Reading…' : 'Parse'}
          </button>
        </div>
        {/* Parse errors sit under the box; the sentence stays so it can be fixed. */}
        {parse.isError && (
          <p className="error" role="alert">
            {parse.error.message}
          </p>
        )}
      </form>

      {savedMessage && (
        <p className="success" role="status">
          Successfully added
        </p>
      )}

      {drafts.map((draft) => (
        <ExpenseCard
          key={draft.id}
          expense={draft.expense}
          onSaved={() => remove(draft.id, true)}
          onDiscard={() => remove(draft.id, false)}
        />
      ))}
    </section>
  )
}
