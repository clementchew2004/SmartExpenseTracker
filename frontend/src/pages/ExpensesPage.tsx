import { useRef, useState } from 'react'
import type { TouchEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { Category, ExpenseRead } from '../api/client'
import { useExpenses } from '../api/hooks'
import { CATEGORIES, formatMoney } from '../api/options'
import { dayLabel, isMonthKey, monthBounds, monthKey, monthLabel, shiftMonth } from '../dates'

type Props = {
  /** An expense waiting out its Undo window: hide it as if already gone. */
  hiddenId: number | null
}

const SWIPE_MIN_PX = 60

/** All expenses for one month, newest first, grouped by day. */
export function ExpensesPage({ hiddenId }: Props) {
  // The month and category live in the URL (?month=2026-10&category=Food), so Back,
  // refresh and the edit page's return link all land on the same view.
  const [params, setParams] = useSearchParams()
  // Read the clock once when the page opens, not on every render (keeps render pure).
  const [thisMonth] = useState(() => monthKey(new Date()))
  const month = isMonthKey(params.get('month')) ? params.get('month')! : thisMonth
  const categoryParam = params.get('category')
  const category = (CATEGORIES as readonly string[]).includes(categoryParam ?? '')
    ? (categoryParam as Category)
    : undefined

  const expenses = useExpenses({ ...monthBounds(month), category })
  const visible = (expenses.data ?? []).filter((e) => e.id !== hiddenId)
  const days = groupByDay(visible)

  const monthInput = useRef<HTMLInputElement>(null)
  const touchStart = useRef<{ x: number; y: number } | null>(null)

  function show(next: { month?: string; category?: Category | null }) {
    const newParams = new URLSearchParams(params)
    if (next.month) newParams.set('month', next.month)
    if (next.category === null) newParams.delete('category')
    else if (next.category) newParams.set('category', next.category)
    setParams(newParams, { replace: true })
  }

  // Swipe left = next month, swipe right = previous. Mostly-vertical moves are scrolling.
  function onTouchStart(e: TouchEvent) {
    const t = e.touches[0]
    touchStart.current = { x: t.clientX, y: t.clientY }
  }
  function onTouchEnd(e: TouchEvent) {
    if (!touchStart.current) return
    const t = e.changedTouches[0]
    const dx = t.clientX - touchStart.current.x
    const dy = t.clientY - touchStart.current.y
    touchStart.current = null
    if (Math.abs(dx) >= SWIPE_MIN_PX && Math.abs(dx) > Math.abs(dy) * 2) {
      show({ month: shiftMonth(month, dx < 0 ? 1 : -1) })
    }
  }

  return (
    <section className="expenses" aria-label="Expenses">
      <h1>Your spending</h1>
      <div className="month-nav">
        <button
          type="button"
          className="secondary icon-button"
          aria-label={`Previous month, ${monthLabel(shiftMonth(month, -1))}`}
          onClick={() => show({ month: shiftMonth(month, -1) })}
        >
          ‹
        </button>
        {/* Tapping the month name opens the phone's own month picker. */}
        <button
          type="button"
          className="month-label"
          aria-label={`${monthLabel(month)}, choose a month`}
          onClick={() => monthInput.current?.showPicker?.() ?? monthInput.current?.focus()}
        >
          <h2>{monthLabel(month)}</h2>
        </button>
        <input
          ref={monthInput}
          type="month"
          className="visually-hidden"
          tabIndex={-1}
          aria-hidden="true"
          value={month}
          onChange={(e) => isMonthKey(e.target.value) && show({ month: e.target.value })}
        />
        <button
          type="button"
          className="secondary icon-button"
          aria-label={`Next month, ${monthLabel(shiftMonth(month, 1))}`}
          onClick={() => show({ month: shiftMonth(month, 1) })}
        >
          ›
        </button>
      </div>

      <div className="chips" role="group" aria-label="Category">
        <button
          type="button"
          className="chip"
          aria-pressed={!category}
          onClick={() => show({ category: null })}
        >
          All
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            className="chip"
            aria-pressed={category === c}
            onClick={() => show({ category: c })}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="expense-days" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        {expenses.isPending && <p className="muted">Loading…</p>}
        {expenses.isError && (
          <p className="error" role="alert">
            {expenses.error.message}
          </p>
        )}
        {expenses.isSuccess && visible.length === 0 && (
          <p className="muted empty">
            No {category ? `${category} ` : ''}expenses in {monthLabel(month)}.
          </p>
        )}
        {days.map(([date, items]) => (
          <section key={date} aria-label={dayLabel(date)}>
            <h2 className="day-heading">{dayLabel(date)}</h2>
            <ul className="expense-rows">
              {items.map((expense) => (
                <li key={expense.id}>
                  <Link to={`/expenses/${expense.id}`} className="expense-row">
                    <span className="row-main">
                      <span className="row-merchant">{expense.merchant}</span>
                      <span className="row-meta">
                        {expense.category}
                        {expense.note ? ` · ${expense.note}` : ''}
                      </span>
                    </span>
                    <span className="row-amount">
                      {formatMoney(expense.amount, expense.currency)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {expenses.data && expenses.data.length >= 200 && (
          <p className="muted">Showing the first 200 expenses this month.</p>
        )}
      </div>
    </section>
  )
}

/** The API returns newest first; keep that order and start a group at each new date. */
function groupByDay(expenses: ExpenseRead[]): [string, ExpenseRead[]][] {
  const groups: [string, ExpenseRead[]][] = []
  for (const expense of expenses) {
    const last = groups.at(-1)
    if (last && last[0] === expense.date) last[1].push(expense)
    else groups.push([expense.date, [expense]])
  }
  return groups
}
