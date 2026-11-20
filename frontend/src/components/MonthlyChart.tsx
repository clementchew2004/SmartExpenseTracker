import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import type { Currency } from '../api/client'
import { useMonthlyStats } from '../api/hooks'
import { CURRENCIES, formatMoney } from '../api/options'
import { CATEGORY_SLOT, DRAW_ORDER } from '../categoryColors'
import { monthKey, monthLabel } from '../dates'

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
        <h2>{monthLabel(month)}</h2>
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
