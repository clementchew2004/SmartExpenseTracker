import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import type { Category, Currency } from '../api/client'
import { useMonthlyStats } from '../api/hooks'
import { CURRENCIES, formatMoney } from '../api/options'

// Colours live in index.css (--cat-1 ... --cat-8, --cat-neutral) with separate light and
// dark values, validated for colour-blind separation by the dataviz palette script.
// Only 8 colours pass, so Bills and Other share the neutral grey (the legend names them).
// The ORDER matters: neighbouring slots were validated as neighbours, so slices are
// drawn in this order, not in the API's alphabetical order.
const CATEGORY_SLOT: Record<Category, string> = {
  Transport: 'var(--cat-1)',
  Food: 'var(--cat-2)',
  Groceries: 'var(--cat-3)',
  Travel: 'var(--cat-4)',
  Shopping: 'var(--cat-5)',
  Health: 'var(--cat-6)',
  Subscriptions: 'var(--cat-7)',
  Entertainment: 'var(--cat-8)',
  Bills: 'var(--cat-neutral)',
  Other: 'var(--cat-neutral)',
}
const DRAW_ORDER = Object.keys(CATEGORY_SLOT) as Category[]

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

const MONTH_LABEL = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })

type Props = {
  currency: Currency
  onCurrencyChange: (currency: Currency) => void
}

/** This month's spending by category, one currency at a time (never mixed). */
export function MonthlyChart({ currency, onCurrencyChange }: Props) {
  // Read the clock once when the chart first appears, not on every render.
  const [now] = useState(() => new Date())
  const month = monthKey(now)
  const stats = useMonthlyStats(month)
  // The total comes from the API (SQL SUM), never added up here.
  const total = stats.data?.currency_totals[currency]

  const totals = stats.data?.totals[currency] ?? {}
  const slices = DRAW_ORDER.filter((category) => category in totals).map((category) => ({
    category,
    amount: totals[category]!, // the exact string from the API, used for display
    value: Number(totals[category]), // only for drawing slice sizes, never for maths
  }))

  return (
    <section className="chart" aria-label="This month's spending">
      <div className="chart-header">
        <h2>{MONTH_LABEL.format(now)}</h2>
        <div className="toggle" role="group" aria-label="Currency">
          {CURRENCIES.map((c) => (
            <button
              key={c}
              type="button"
              className={c === currency ? 'active' : ''}
              aria-pressed={c === currency}
              onClick={() => onCurrencyChange(c)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {stats.isPending && <p className="muted">Loading…</p>}
      {stats.isError && (
        <p className="error" role="alert">
          {stats.error.message}
        </p>
      )}
      {stats.isSuccess && slices.length === 0 && (
        <p className="muted">No {currency} spending this month yet.</p>
      )}

      {slices.length > 0 && (
        <>
          {/* The legend below is the text version; this label summarises the picture. */}
          <div
            className="chart-canvas"
            role="img"
            aria-label={`${currency} spending by category: ${slices
              .map((slice) => `${slice.category} ${formatMoney(slice.amount, currency)}`)
              .join(', ')}`}
          >
            {total !== undefined && (
              <p className="donut-total">
                <span className="donut-total-label">Total</span>
                {formatMoney(total, currency)}
              </p>
            )}
            <ResponsiveContainer width="100%" height="100%">
              <PieChart accessibilityLayer={false}>
                <Pie data={slices} dataKey="value" nameKey="category" innerRadius="55%" isAnimationActive={false}>
                  {slices.map((slice) => (
                    <Cell key={slice.category} style={{ fill: CATEGORY_SLOT[slice.category] }} />
                  ))}
                </Pie>
                <Tooltip formatter={(_value, _name, item) => formatMoney(item.payload.amount, currency)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="legend">
            {slices.map((slice) => (
              <li key={slice.category}>
                <span className="swatch" style={{ background: CATEGORY_SLOT[slice.category] }} />
                <span>{slice.category}</span>
                <span className="legend-amount">{formatMoney(slice.amount, currency)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
