import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { Category, Currency, TrendMonth } from '../api/client'
import { useSpendingTrend } from '../api/hooks'
import { CURRENCIES, formatMoney } from '../api/options'
import { CATEGORY_SLOT, DRAW_ORDER } from '../categoryColors'
import { shortMonthLabel } from '../dates'

/** The last six months on the Insights page, ending at the month the arrows
 * show. Every number comes from the API; the browser only draws them. */
export function TrendCharts({ month }: { month: string }) {
  const [currency, setCurrency] = useState<Currency>('GBP')
  const trend = useSpendingTrend(month)
  const months = trend.data?.currencies.find((c) => c.currency === currency)?.months ?? []
  const spentAnything = months.some((m) => Number(m.total ?? 0) > 0)

  return (
    <section className="chart trend" aria-label="Last 6 months">
      <div className="chart-header">
        <h2>Last 6 months</h2>
        <div className="toggle" role="group" aria-label="Currency">
          {CURRENCIES.map((c) => (
            <button
              key={c}
              type="button"
              className={c === currency ? 'active' : ''}
              aria-pressed={c === currency}
              onClick={() => setCurrency(c)}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      {trend.isPending && <p className="muted">Loading…</p>}
      {trend.isError && (
        <p className="error" role="alert">
          {trend.error.message}
        </p>
      )}
      {trend.isSuccess && !spentAnything && (
        <p className="muted">
          No {currency} spending from {shortMonthLabel(months[0].month)} to{' '}
          {shortMonthLabel(months[5].month)}.
        </p>
      )}

      {spentAnything && (
        <>
          <SpendingLine months={months} currency={currency} />
          <CategoryBars months={months} currency={currency} />
        </>
      )}
    </section>
  )
}

// --- Shared chart pieces ------------------------------------------------------------

const AXIS = { fontSize: 12, fill: 'var(--muted)' }

/** Clean y-axis ticks: £0 / £250 / £500, no pennies. */
function axisMoney(currency: Currency) {
  return (value: number) => (currency === 'GBP' ? `£${value}` : `RM ${value}`)
}

/** "Oct" on the axis; the year only when the six months cross New Year. */
function axisMonth(months: TrendMonth[]) {
  const crossesYear = months[0].month.slice(0, 4) !== months[5].month.slice(0, 4)
  return (key: string) => (crossesYear ? shortMonthLabel(key) : shortMonthLabel(key).split(' ')[0])
}

/** Screen readers get the numbers as a table instead of a picture. */
function ScreenReaderTable({
  caption,
  head,
  rows,
}: {
  caption: string
  head: string[]
  rows: string[][]
}) {
  return (
    <table className="visually-hidden">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row[0]}>
            {row.map((cell, i) => (i === 0 ? <th key={i}>{cell}</th> : <td key={i}>{cell}</td>))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// --- Spending per month, with the budget as a step line ------------------------------

function SpendingLine({ months, currency }: { months: TrendMonth[]; currency: Currency }) {
  const hasBudget = months.some((m) => m.budget !== null)
  const data = months.map((m) => ({
    month: m.month,
    // null = a month that hasn't started: no point, not £0.
    spent: m.total === null ? null : Number(m.total),
    budget: m.budget === null ? null : Number(m.budget),
  }))

  return (
    <figure className="trend-figure">
      <figcaption className="trend-caption">
        <span>Spent per month</span>
        {/* Two series, so a legend; identity never by colour alone. */}
        {hasBudget && (
          <span className="line-legend" aria-hidden="true">
            <span className="line-key line-key-spent" /> Spent
            <span className="line-key line-key-budget" /> Budget
          </span>
        )}
      </figcaption>
      <div className="trend-canvas" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
            // The hidden table gives screen readers the numbers; without this, Recharts
            // makes ~30 focusable points inside an area marked aria-hidden.
            accessibilityLayer={false}
          >
            <CartesianGrid vertical={false} stroke="var(--border)" strokeWidth={1} />
            <XAxis
              dataKey="month"
              tickFormatter={axisMonth(months)}
              tick={AXIS}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tickFormatter={axisMoney(currency)}
              tick={AXIS}
              axisLine={false}
              tickLine={false}
              width={56}
              allowDecimals={false}
            />
            {/* Each month's own budget as a flat step: it jumps where it changed,
                instead of sloping between months as if it had been in between. */}
            {hasBudget && (
              <Line
                dataKey="budget"
                type="step"
                stroke="var(--muted)"
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
                activeDot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
            <Line
              dataKey="spent"
              type="linear"
              stroke="var(--accent)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={{ r: 4, fill: 'var(--accent)', stroke: 'var(--bg)', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: 'var(--accent)', stroke: 'var(--bg)', strokeWidth: 2 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            {/* Your choice: tapping a point shows just the exact amount. */}
            <Tooltip
              cursor={{ stroke: 'var(--border)' }}
              content={({ active, payload, label }) => {
                const spent = payload?.find((p) => p.dataKey === 'spent')?.value
                if (!active || spent == null) return null
                return (
                  <div className="chart-tooltip">
                    <span className="muted">{shortMonthLabel(String(label))}</span>
                    <strong>{formatMoney(Number(spent).toFixed(2), currency)}</strong>
                  </div>
                )
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ScreenReaderTable
        caption={`${currency} spent per month`}
        head={hasBudget ? ['Month', 'Spent', 'Budget'] : ['Month', 'Spent']}
        rows={months.map((m) => {
          const row = [
            shortMonthLabel(m.month),
            m.total === null ? 'Not yet' : formatMoney(m.total, currency),
          ]
          if (hasBudget) row.push(m.budget === null ? 'None' : formatMoney(m.budget, currency))
          return row
        })}
      />
    </figure>
  )
}

// --- What it went on: categories stacked per month ------------------------------------

function CategoryBars({ months, currency }: { months: TrendMonth[]; currency: Currency }) {
  // Only categories used in these six months, in the donut's fixed colour order.
  const used = DRAW_ORDER.filter((c) => months.some((m) => m.by_category[c]))
  const data = months.map((m) => ({
    month: m.month,
    ...Object.fromEntries(used.map((c) => [c, Number(m.by_category[c] ?? 0)])),
  }))

  return (
    <figure className="trend-figure">
      <figcaption className="trend-caption">
        <span>What it went on</span>
      </figcaption>
      <div className="trend-canvas" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
            // The hidden table gives screen readers the numbers; without this, Recharts
            // makes ~30 focusable points inside an area marked aria-hidden.
            accessibilityLayer={false}
          >
            <CartesianGrid vertical={false} stroke="var(--border)" strokeWidth={1} />
            <XAxis
              dataKey="month"
              tickFormatter={axisMonth(months)}
              tick={AXIS}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tickFormatter={axisMoney(currency)}
              tick={AXIS}
              axisLine={false}
              tickLine={false}
              width={56}
              allowDecimals={false}
            />
            {used.map((category) => (
              <Bar
                key={category}
                dataKey={category}
                stackId="month"
                fill={CATEGORY_SLOT[category]}
                // A 2px gap in the background colour between segments, like the donut.
                stroke="var(--bg)"
                strokeWidth={2}
                maxBarSize={24}
                isAnimationActive={false}
              />
            ))}
            <Tooltip
              cursor={{ fill: 'var(--border)', opacity: 0.4 }}
              content={({ active, payload, label }) => {
                if (!active || !payload) return null
                const parts = payload.filter((p) => Number(p.value) > 0).reverse()
                if (parts.length === 0) return null
                const month = months.find((m) => m.month === label)
                return (
                  <div className="chart-tooltip">
                    <span className="muted">{shortMonthLabel(String(label))}</span>
                    <ul>
                      {parts.map((p) => (
                        <li key={String(p.dataKey)}>
                          <span
                            className="swatch"
                            style={{ background: CATEGORY_SLOT[p.dataKey as Category] }}
                          />
                          {String(p.dataKey)}
                          <span className="legend-amount">
                            {formatMoney(Number(p.value).toFixed(2), currency)}
                          </span>
                        </li>
                      ))}
                    </ul>
                    {month?.total && <strong>Total {formatMoney(month.total, currency)}</strong>}
                  </div>
                )
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* More than one series, so a legend; Bills and Other share grey, named here. */}
      <ul className="legend legend-inline" aria-hidden="true">
        {used.map((c) => (
          <li key={c}>
            <span className="swatch" style={{ background: CATEGORY_SLOT[c] }} />
            {c}
          </li>
        ))}
      </ul>
      <ScreenReaderTable
        caption={`${currency} spending per category per month`}
        head={['Month', ...used]}
        rows={months.map((m) => [
          shortMonthLabel(m.month),
          ...used.map((c) => formatMoney(m.by_category[c] ?? '0.00', currency)),
        ])}
      />
    </figure>
  )
}
