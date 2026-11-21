import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'

import type { Category, Currency } from '../api/client'
import { useMonthlyStats } from '../api/hooks'
import { CURRENCIES, formatMoney } from '../api/options'
import { CATEGORY_SLOT, DRAW_ORDER } from '../categoryColors'
import { monthKey, monthLabel } from '../dates'
import { CategoryRanking } from './CategoryRanking'

type Props = {
  currency: Currency
  onCurrencyChange: (currency: Currency) => void
}

/** This month's spending: a pie of the categories with the total in the middle,
 * and the categories ranked beside it as its legend. One currency at a time
 * (never mixed). */
export function MonthlyChart({ currency, onCurrencyChange }: Props) {
  // Read the clock once when the chart first appears, not on every render.
  const [now] = useState(() => new Date())
  const month = monthKey(now)
  const stats = useMonthlyStats(month)
  // The total comes from the API (SQL SUM), never added up here.
  const total = stats.data?.currency_totals[currency]
  const totals = stats.data?.totals[currency] ?? {}
  // Slices in the palette's fixed order: neighbours were validated as neighbours.
  const slices = DRAW_ORDER.filter((category) => category in totals).map((category) => ({
    category,
    amount: totals[category]!, // the exact string from the API, used for display
    value: Number(totals[category]), // only for drawing slice sizes, never for maths
  }))
  const rows = (Object.keys(totals) as Category[]).map((category) => ({
    category,
    amount: totals[category]!,
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
      {stats.isSuccess && rows.length === 0 && (
        <p className="muted">No {currency} spending this month yet.</p>
      )}

      {rows.length > 0 && total !== undefined && (
        <>
          {/* The ranked list below names every slice; this label sums up the picture. */}
          <div
            className="pie"
            role="img"
            aria-label={`${currency} spending by category: ${slices
              .map((s) => `${s.category} ${formatMoney(s.amount, currency)}`)
              .join(', ')}`}
          >
            {/* The month's total is this screen's main figure: the signature colour. */}
            <p className="pie-total">
              <span className="month-total-label">Spent so far</span>
              <span className="month-total-value">{formatMoney(total, currency)}</span>
            </p>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart accessibilityLayer={false}>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="category"
                  innerRadius="70%"
                  outerRadius="100%"
                  isAnimationActive={false}
                >
                  {slices.map((s) => (
                    <Cell key={s.category} style={{ fill: CATEGORY_SLOT[s.category] }} />
                  ))}
                </Pie>
                <Tooltip formatter={(_v, _n, item) => formatMoney(item.payload.amount, currency)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <CategoryRanking rows={rows} currency={currency} colours={CATEGORY_SLOT} />
        </>
      )}
    </section>
  )
}
