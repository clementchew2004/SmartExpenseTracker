import { useState } from 'react'
import type { FormEvent } from 'react'

import type { Category, Currency, RepeatRead } from '../api/client'
import { useDeleteRepeat, useRepeats, useUpdateRepeat } from '../api/hooks'
import { CATEGORIES, CURRENCIES, FREQUENCY_LABEL, formatMoney } from '../api/options'
import { dayLabel } from '../dates'

/** Settings: every repeating expense, with Edit and Stop. */
export function RepeatList() {
  const repeats = useRepeats()

  return (
    <section className="repeat-list" aria-label="Repeating expenses">
      <h2 className="settings-heading">Repeating expenses</h2>
      {repeats.isPending && <p className="muted">Loading…</p>}
      {repeats.isError && <p className="error">{repeats.error.message}</p>}
      {repeats.data?.length === 0 && (
        <p className="muted">None yet. Tick "Repeat" on an expense card to add one.</p>
      )}
      {repeats.data?.map((r) => <RepeatCard key={r.id} repeat={r} />)}
    </section>
  )
}

function RepeatCard({ repeat }: { repeat: RepeatRead }) {
  const [mode, setMode] = useState<'view' | 'edit' | 'confirm-stop'>('view')
  const stop = useDeleteRepeat()

  if (mode === 'edit') return <EditRepeat repeat={repeat} onDone={() => setMode('view')} />

  return (
    <article className="card repeat-card" aria-label={`Repeating: ${repeat.merchant}`}>
      <p className="reminder-summary">
        <strong>{repeat.merchant}</strong>
        <span>{formatMoney(repeat.amount, repeat.currency)}</span>
      </p>
      <p className="muted">
        {FREQUENCY_LABEL[repeat.frequency]} ·{' '}
        {repeat.finished ? 'Ended' : `next ${dayLabel(repeat.next_due)}`}
        {repeat.end_date && !repeat.finished && ` · ends ${dayLabel(repeat.end_date)}`}
      </p>

      {mode === 'confirm-stop' ? (
        <div className="confirm">
          <p>Stop repeating {repeat.merchant}? Expenses already saved stay.</p>
          {stop.isError && <p className="error">{stop.error.message}</p>}
          <div className="card-actions">
            <button type="button" className="secondary" onClick={() => setMode('view')}>
              Cancel
            </button>
            <button
              type="button"
              className="danger"
              disabled={stop.isPending}
              onClick={() => stop.mutate(repeat.id)}
            >
              {stop.isPending ? 'Stopping…' : 'Stop'}
            </button>
          </div>
        </div>
      ) : (
        // Same as every Settings row: Edit, then the destructive action, together on the right.
        <div className="row-actions">
          <button type="button" className="secondary small" onClick={() => setMode('edit')}>
            Edit
          </button>
          <button
            type="button"
            className="secondary small"
            onClick={() => setMode('confirm-stop')}
          >
            Stop
          </button>
        </div>
      )}
    </article>
  )
}

/** Changes future reminders only. How often can't change: stop it and add a new one. */
function EditRepeat({ repeat, onDone }: { repeat: RepeatRead; onDone: () => void }) {
  const [amount, setAmount] = useState(repeat.amount)
  const [currency, setCurrency] = useState<Currency>(repeat.currency)
  const [merchant, setMerchant] = useState(repeat.merchant)
  const [category, setCategory] = useState<Category>(repeat.category)
  const [endDate, setEndDate] = useState(repeat.end_date ?? '')
  const update = useUpdateRepeat()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      await update.mutateAsync({
        id: repeat.id,
        changes: { amount, currency, merchant, category, end_date: endDate || null },
      })
      onDone()
    } catch {
      // The error is shown from update.error below.
    }
  }

  return (
    <form className="card repeat-card" onSubmit={handleSubmit}>
      <p className="muted">
        Editing {repeat.merchant} ({FREQUENCY_LABEL[repeat.frequency].toLowerCase()}). Changes apply
        to future reminders only.
      </p>
      <div className="card-fields">
        <label>
          Amount
          <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label>
          Currency
          <select value={currency} onChange={(e) => setCurrency(e.target.value as Currency)}>
            {CURRENCIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Merchant
          <input value={merchant} onChange={(e) => setMerchant(e.target.value)} />
        </label>
        <label>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value as Category)}>
            {CATEGORIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Ends <span className="hint">(optional)</span>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </label>
      </div>
      {update.isError && (
        <p className="error" role="alert">
          {update.error.message}
        </p>
      )}
      <div className="card-actions">
        <button type="button" className="secondary" onClick={onDone}>
          Cancel
        </button>
        <button type="submit" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </form>
  )
}
