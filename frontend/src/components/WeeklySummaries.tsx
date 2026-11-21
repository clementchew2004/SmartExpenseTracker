import { useEffect, useId, useRef, useState } from 'react'

import type { Currency, CurrencyWeek, WeekSummary } from '../api/client'
import { streamWeekSentence } from '../api/client'
import { useWeeklyInsights } from '../api/hooks'
import { formatMoney } from '../api/options'
import { monthKey, weekLabel } from '../dates'
import { ChangeArrow, Chevron } from './Icon'

type Props = {
  /** The chart's GBP/MYR choice: the numbers line follows it. */
  currency: Currency
}

/** This month's weeks, newest first: numbers from SQL, and an AI sentence on tap. */
export function WeeklySummaries({ currency }: Props) {
  // Read the clock once when this first appears, like the chart.
  const [now] = useState(() => new Date())
  const weeks = useWeeklyInsights(monthKey(now))

  return (
    <section className="weekly" aria-label="This month's weeks" aria-busy={weeks.isPending}>
      <h2>This month's weeks</h2>
      {weeks.isPending && (
        <>
          {/* The AI may be writing: grey cards where the real ones will appear. */}
          <p className="visually-hidden" role="status">
            Writing your weekly summaries
          </p>
          {[1, 2].map((n) => (
            <div key={n} className="card skeleton" aria-hidden="true">
              <span className="skeleton-line skeleton-short" />
              <span className="skeleton-line" />
              <span className="skeleton-line" />
            </div>
          ))}
        </>
      )}
      {weeks.isError && (
        <p className="error" role="alert">
          {weeks.error.message}
        </p>
      )}
      {weeks.data?.weeks.map((week) => (
        <WeekCard key={week.week_start} week={week} month={weeks.data.month} currency={currency} />
      ))}
    </section>
  )
}

function WeekCard({
  week,
  month,
  currency,
}: {
  week: WeekSummary
  month: string
  currency: Currency
}) {
  const numbers = week.currencies.find((c) => c.currency === currency)
  const spentAnything = week.currencies.some((c) => Number(c.spent) > 0)
  const label = weekLabel(week.week_start, week.week_end)

  return (
    <article className="card week-card" aria-label={`Week of ${label}`}>
      <p className="week-heading">
        {label}
        {week.in_progress && <span className="muted"> · so far</span>}
      </p>
      <p className="week-numbers">
        {numbers && Number(numbers.spent) > 0 ? (
          numbersLine(numbers, week.compared_with ?? null)
        ) : (
          <span className="muted">No {currency} spending this week</span>
        )}
      </p>
      {numbers && numbers.top_merchants.length > 0 && (
        <p className="week-merchants muted">
          Top:{' '}
          {numbers.top_merchants
            .map((m) => `${m.merchant} ${formatMoney(m.spent, numbers.currency)}`)
            .join(' · ')}
        </p>
      )}
      {/* Keyed by the numbers: if they change (a new expense), the old
          sentence no longer fits, so this starts fresh. */}
      {spentAnything && (
        <Sentence key={JSON.stringify(week.currencies)} week={week} month={month} />
      )}
    </article>
  )
}

type Writing = 'idle' | 'writing' | 'done' | 'failed'

/**
 * "Summary": the AI is only asked when you open it, and its words appear as
 * they're written. A sentence already saved for these numbers shows at once.
 *
 * Plain component state rather than TanStack Query: a query holds one finished
 * answer, but here the text grows piece by piece while it streams.
 */
function Sentence({ week, month }: { week: WeekSummary; month: string }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(week.summary ?? '')
  const [state, setState] = useState<Writing>(week.summary ? 'done' : 'idle')
  const cancel = useRef<AbortController | null>(null)
  const id = useId()

  // Leaving the page mid-stream: stop reading (the server then stops too).
  useEffect(() => () => cancel.current?.abort(), [])

  async function write() {
    cancel.current?.abort()
    const controller = new AbortController()
    cancel.current = controller
    setText('')
    setState('writing')
    try {
      await streamWeekSentence(
        week.week_start,
        month,
        (piece) => setText((t) => t + piece),
        controller.signal,
      )
      setState('done')
    } catch {
      if (!controller.signal.aborted) setState('failed')
    }
  }

  function toggle() {
    setOpen((o) => !o)
    if (!open && state === 'idle') void write()
  }

  return (
    <div className="week-sentence">
      <button
        type="button"
        className="secondary small week-toggle"
        aria-expanded={open}
        aria-controls={id}
        onClick={toggle}
      >
        <Chevron direction={open ? 'down' : 'right'} size={16} /> Summary
      </button>
      {open && (
        // aria-live: screen readers hear the sentence once, when it settles.
        <div id={id} aria-live="polite" aria-busy={state === 'writing'}>
          {state === 'writing' && !text && <span className="skeleton-line" aria-hidden="true" />}
          {text && (
            <p
              className={[
                'week-text',
                state === 'writing' ? 'writing' : '',
                state === 'failed' ? 'unfinished' : '',
              ].join(' ')}
            >
              {text}
            </p>
          )}
          {state === 'failed' && (
            <p className="muted week-text">
              {text ? "Couldn't finish the summary." : "Couldn't write a summary right now."}{' '}
              <button type="button" className="secondary small" onClick={() => void write()}>
                Try again
              </button>
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/** "£67.10 · up £28.90 (76%) vs last week · 9% of budget". Parts without a value
 * are left out. Every number comes from the API; nothing is calculated here. */
function numbersLine(c: CurrencyWeek, comparedWith: string | null) {
  const parts = [<strong key="spent">{formatMoney(c.spent, c.currency)}</strong>]

  if (c.change != null && comparedWith) {
    const change = Number(c.change)
    const pct = c.change_pct != null ? ` (${Math.abs(c.change_pct)}%)` : ''
    const amount = formatMoney(c.change.replace('-', ''), c.currency)
    const against = comparedWith.replace('the same', 'same')
    parts.push(
      change === 0 ? (
        <span key="change">same as {against}</span>
      ) : (
        <span key="change">
          {/* Spending going up is the bad direction, so it's red; down is green.
              The arrow is decoration; screen readers hear "up" / "down". */}
          <span className={change > 0 ? 'change-bad' : 'change-good'}>
            <ChangeArrow up={change > 0} />
          </span>{' '}
          <span className="visually-hidden">{change > 0 ? 'up ' : 'down '}</span>
          {amount}
          {pct} vs {against}
        </span>
      ),
    )
  }
  if (c.budget_share_pct != null) {
    parts.push(<span key="budget">{c.budget_share_pct}% of budget</span>)
  }

  return parts.flatMap((part, i) => (i === 0 ? [part] : [<span key={`dot${i}`}> · </span>, part]))
}
