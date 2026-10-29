import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { Currency, ExpenseCreate } from '../api/client'
import { useCreateExpense, useCreateRepeat, useParseText } from '../api/hooks'
import { FREQUENCY_LABEL, formatMoney } from '../api/options'
import { ExpenseCard } from './ExpenseCard'
import type { RepeatChoice } from './RepeatOptions'

type Draft = {
  id: string
  expense: ExpenseCreate
  repeat: RepeatChoice
  editing: boolean
  saving: boolean
  error: string | null
}
type Notice = { text: string; undo?: { draft: Draft; index: number } }

// Card ids only need to be unique on screen. (Not crypto.randomUUID(): browsers only
// provide it on HTTPS/localhost, so it crashed when testing on a phone over Wi-Fi.)
let nextDraftId = 0

type Props = {
  /** Told after each save, so the chart can show that currency. */
  onSaved: (currency: Currency) => void
}

/** The main screen's top half: sentence in, editable cards out. */
export function QuickAdd({ onSaved }: Props) {
  const [text, setText] = useState('')
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [notice, setNotice] = useState<Notice | null>(null)
  const parse = useParseText()
  const save = useCreateExpense()
  const createRepeat = useCreateRepeat()
  const inputRef = useRef<HTMLInputElement>(null)
  const savedThisRound = useRef(false)

  // Most parses take 1-2s; if one is still going after 4s, say so instead of looking stuck.
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!parse.isPending) return
    const timer = setTimeout(() => setSlow(true), 4000)
    return () => clearTimeout(timer)
  }, [parse.isPending])

  // Hide the "Saved…" / "Discarded… Undo" bar after a few seconds.
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(null), 5000)
    return () => clearTimeout(timer)
  }, [notice])

  // Every card dealt with: clear the box for the next expense, but only if something
  // was saved. Discarding everything keeps the sentence so it can be reworded.
  const hadDrafts = useRef(false)
  useEffect(() => {
    if (hadDrafts.current && drafts.length === 0 && savedThisRound.current) setText('')
    hadDrafts.current = drafts.length > 0
  }, [drafts])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!text.trim() || parse.isPending) return
    setNotice(null)
    setSlow(false)
    savedThisRound.current = false
    parse.mutate(text, {
      onSuccess: (result) =>
        setDrafts(
          result.expenses.map((parsed) => ({
            id: String(++nextDraftId),
            // The API only returns parsed expenses that have an amount.
            expense: { ...parsed, amount: parsed.amount ?? '' },
            repeat: null,
            editing: false,
            saving: false,
            error: null,
          })),
        ),
    })
  }

  // All updates are functional (setDrafts(current => ...)) so overlapping saves and
  // discards always start from the latest list.
  function patch(id: string, changes: Partial<Draft>) {
    setDrafts((current) => current.map((d) => (d.id === id ? { ...d, ...changes } : d)))
  }

  function change<K extends keyof ExpenseCreate>(id: string, field: K, value: ExpenseCreate[K]) {
    setDrafts((current) =>
      current.map((d) => (d.id === id ? { ...d, expense: { ...d.expense, [field]: value } } : d)),
    )
  }

  /** Save one card. Returns whether it worked; on failure the card keeps the error. */
  async function saveDraft(draft: Draft): Promise<boolean> {
    const { repeat } = draft
    // Checked here too, so a bad end date can't leave a saved expense without its repeat.
    if (repeat?.end_date && repeat.end_date < draft.expense.date) {
      patch(draft.id, { error: "The repeat can't end before the expense's date" })
      return false
    }
    patch(draft.id, { saving: true, error: null })
    try {
      await save.mutateAsync(draft.expense)
    } catch (error) {
      // Open the fields so the user can fix the problem straight away.
      patch(draft.id, {
        saving: false,
        editing: true,
        error: error instanceof Error ? error.message : 'Could not save',
      })
      return false
    }
    savedThisRound.current = true
    setDrafts((current) => current.filter((d) => d.id !== draft.id))
    onSaved(draft.expense.currency)

    // The expense is saved; now set up its repeat (the expense's date is the first one).
    if (repeat) {
      try {
        await createRepeat.mutateAsync({
          ...draft.expense,
          frequency: repeat.frequency,
          end_date: repeat.end_date || null,
        })
      } catch (error) {
        // Don't offer Save again: that would save the expense a second time.
        setNotice({
          text: `Saved ${draft.expense.merchant}, but the repeat wasn't set up: ${
            error instanceof Error ? error.message : 'unknown error'
          }`,
        })
        return false
      }
    }
    return true
  }

  async function handleSave(draft: Draft) {
    if (await saveDraft(draft)) {
      const { amount, currency, category } = draft.expense
      const repeats = draft.repeat ? ` · repeats ${FREQUENCY_LABEL[draft.repeat.frequency].toLowerCase()}` : ''
      setNotice({ text: `Saved ${formatMoney(String(amount), currency)} · ${category}${repeats}` })
      inputRef.current?.focus()
    }
  }

  async function handleSaveAll() {
    let saved = 0
    for (const draft of drafts) {
      if (await saveDraft(draft)) saved++
    }
    if (saved > 0) setNotice({ text: `Saved ${saved} expense${saved === 1 ? '' : 's'}` })
    inputRef.current?.focus()
  }

  function handleDiscard(draft: Draft) {
    const index = drafts.findIndex((d) => d.id === draft.id)
    setDrafts((current) => current.filter((d) => d.id !== draft.id))
    setNotice({ text: `Discarded ${draft.expense.merchant}`, undo: { draft, index } })
    inputRef.current?.focus()
  }

  function undoDiscard(undo: NonNullable<Notice['undo']>) {
    setDrafts((current) => {
      const next = [...current]
      next.splice(Math.min(undo.index, next.length), 0, undo.draft)
      return next
    })
    setNotice(null)
  }

  return (
    <section className="quick-add" aria-label="Add an expense" aria-busy={parse.isPending}>
      {/* Screen readers hear the wait start, and hear if it is taking a while. */}
      <p className="visually-hidden" role="status">
        {parse.isPending ? (slow ? 'Still reading your expense' : 'Reading your expense') : ''}
      </p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="expense-text" className="visually-hidden">
          Describe what you spent
        </label>
        <div className="input-row">
          <input
            id="expense-text"
            ref={inputRef}
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
        {parse.isPending && slow && (
          <p className="muted waiting-note">Still working - the AI is slower than usual.</p>
        )}
      </form>

      {/* A placeholder card where the real ones will appear. */}
      {parse.isPending && (
        <div className="card skeleton" aria-hidden="true">
          <span className="skeleton-line skeleton-amount" />
          <span className="skeleton-line" />
          <span className="skeleton-line skeleton-short" />
        </div>
      )}

      {notice && (
        <div className="notice" role="status">
          <span>{notice.text}</span>
          {notice.undo && (
            <button type="button" className="link" onClick={() => undoDiscard(notice.undo!)}>
              Undo
            </button>
          )}
        </div>
      )}

      {drafts.map((draft) => (
        <ExpenseCard
          key={draft.id}
          expense={draft.expense}
          editing={draft.editing}
          saving={draft.saving}
          error={draft.error}
          onToggleEdit={() => patch(draft.id, { editing: !draft.editing })}
          onChange={(field, value) => change(draft.id, field, value)}
          repeat={draft.repeat}
          onRepeatChange={(repeat) => patch(draft.id, { repeat })}
          onSave={() => handleSave(draft)}
          onDiscard={() => handleDiscard(draft)}
        />
      ))}

      {drafts.length >= 2 && (
        <button
          type="button"
          className="save-all"
          onClick={handleSaveAll}
          disabled={drafts.some((d) => d.saving)}
        >
          Save {drafts.length} expenses
        </button>
      )}
    </section>
  )
}
