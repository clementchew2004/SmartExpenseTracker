import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { CategoryChange, Currency, PaceDay, TrendMonth } from '../api/client'
import { useBudgetPace, useCategoryChanges, useSpendingTrend } from '../api/hooks'
import { CURRENCIES, formatMoney } from '../api/options'
import { dayLabel, monthLabel, shortMonthLabel } from '../dates'
import { ChangeArrow } from './Icon'

/** The Insights graphs for the month the arrows show: this month's pace against
 * the budget, the six months ending there, and what changed against your usual.
 * Every number comes from the API; the browser only draws them. */
export function TrendCharts({ month }: { month: string }) {
  const [currency, setCurrency] = useState<Currency>('GBP')
  const trend = useSpendingTrend(month)
  const months = trend.data?.currencies.find((c) => c.currency === currency)?.months ?? []
  const spentAnything = months.some((m) => Number(m.total ?? 0) > 0)

  return (
    <section className="chart trend" aria-label="Spending graphs">
      <div className="chart-header">
        <h2>Your spending</h2>
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

      <PaceLine month={month} currency={currency} />

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
      {spentAnything && <SpendingLine months={months} currency={currency} />}

      <ChangeBars month={month} currency={currency} />
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
    // In a hidden <div>, not a hidden <table>: tables ignore the 1px width that
    // .visually-hidden relies on, and this one stretched the page to ~720px.
    <div className="visually-hidden">
      <table>
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
    </div>
  )
}

// --- Spending per month, with the budget as a step line ------------------------------

function SpendingLine({ months, currency }: { months: TrendMonth[]; currency: Currency }) {
  // Months before your first spending are "not tracked yet", not "spent £0": the
  // line starts at your first month instead of running flat along the bottom.
  const first = months.findIndex((m) => Number(m.total ?? 0) > 0)
  const tracked = (i: number) => i >= first
  const hasBudget = months.some((m, i) => tracked(i) && m.budget !== null)
  const data = months.map((m, i) => ({
    month: m.month,
    // null = no point: a month that hasn't started, or one before you started.
    spent: m.total === null || !tracked(i) ? null : Number(m.total),
    budget: m.budget === null || !tracked(i) ? null : Number(m.budget),
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
              stroke="var(--data)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={{ r: 4, fill: 'var(--data)', stroke: 'var(--bg)', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: 'var(--data)', stroke: 'var(--bg)', strokeWidth: 2 }}
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
        rows={months.map((m, i) => {
          if (!tracked(i)) {
            const row = [shortMonthLabel(m.month), 'Not tracked yet']
            if (hasBudget) row.push('None')
            return row
          }
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

// --- Budget pace: the month so far, against an even pace to the budget -------------

/** "22 Nov" from "2026-11-22". */
function shortDay(isoDate: string) {
  return dayLabel(isoDate).split(' ').slice(1).join(' ')
}

function PaceLine({ month, currency }: { month: string; currency: Currency }) {
  const pace = useBudgetPace(month)
  const chosen = pace.data?.currencies.find((c) => c.currency === currency)
  const days: PaceDay[] = chosen?.days ?? []
  const hasBudget = chosen?.budget != null
  // The last day with a point: today in this month, the last day in a past one.
  const latest = days.filter((d) => d.spent !== null).at(-1)
  const data = days.map((d) => ({
    date: d.date,
    // Only for drawing: every number shown in words is the API's exact string.
    spent: d.spent === null ? null : Number(d.spent),
    onPace: d.on_pace === null ? null : Number(d.on_pace),
  }))
  const lastDay = days.at(-1)?.date
  const ticks = days.length
    ? [days[0].date, days[7].date, days[14].date, days[21].date, lastDay!]
    : []

  return (
    <figure className="trend-figure">
      <figcaption className="trend-caption">
        <span>{shortMonthLabel(month).split(' ')[0]}, day by day</span>
        {hasBudget && (
          <span className="line-legend" aria-hidden="true">
            <span className="line-key line-key-spent" /> Spent
            <span className="line-key line-key-budget" /> Even pace
          </span>
        )}
      </figcaption>

      {pace.isPending && <p className="muted">Loading…</p>}
      {pace.isError && (
        <p className="error" role="alert">
          {pace.error.message}
        </p>
      )}
      {pace.isSuccess && !latest && (
        <p className="muted">{monthLabel(month)} hasn't started yet.</p>
      )}

      {latest && (
        <>
          {/* The takeaway in words: where you are against where an even pace would be. */}
          <p className="pace-summary">
            <strong>{formatMoney(latest.spent!, currency)}</strong> spent by{' '}
            {shortDay(latest.date)}
            {latest.on_pace !== null && (
              <span className="muted"> · even pace {formatMoney(latest.on_pace, currency)}</span>
            )}
          </p>
          <div className="trend-canvas" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
                accessibilityLayer={false}
              >
                <CartesianGrid vertical={false} stroke="var(--border)" strokeWidth={1} />
                <XAxis
                  dataKey="date"
                  ticks={ticks}
                  tickFormatter={(d: string) => String(Number(d.slice(8, 10)))}
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
                {hasBudget && (
                  <Line
                    dataKey="onPace"
                    type="linear"
                    stroke="var(--muted)"
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    dot={false}
                    activeDot={false}
                    isAnimationActive={false}
                  />
                )}
                <Line
                  dataKey="spent"
                  type="stepAfter"
                  stroke="var(--data)"
                  strokeWidth={2}
                  strokeLinejoin="round"
                  dot={false}
                  activeDot={{ r: 5, fill: 'var(--data)', stroke: 'var(--bg)', strokeWidth: 2 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
                <Tooltip
                  cursor={{ stroke: 'var(--border)' }}
                  content={({ active, payload, label }) => {
                    const spent = payload?.find((p) => p.dataKey === 'spent')?.value
                    if (!active || spent == null) return null
                    return (
                      <div className="chart-tooltip">
                        <span className="muted">{shortDay(String(label))}</span>
                        <strong>{formatMoney(Number(spent).toFixed(2), currency)}</strong>
                      </div>
                    )
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {!hasBudget && (
            <p className="hint">Set a {currency} budget above to compare with an even pace.</p>
          )}
          <ScreenReaderTable
            caption={`${currency} spent so far, day by day`}
            head={hasBudget ? ['Day', 'Spent so far', 'Even pace'] : ['Day', 'Spent so far']}
            rows={days
              .filter((d) => d.spent !== null)
              .map((d) => {
                const row = [shortDay(d.date), formatMoney(d.spent!, currency)]
                if (hasBudget) row.push(formatMoney(d.on_pace!, currency))
                return row
              })}
          />
        </>
      )}
    </figure>
  )
}

// --- Changes vs usual: each category against your recent average -------------------

/** "Usual = your average for Sep–Oct, over days 1–22 of each month." */
function usualLabel(months: string[], upToDay: number | null | undefined) {
  const first = shortMonthLabel(months[0]).split(' ')[0]
  const last = shortMonthLabel(months[months.length - 1]).split(' ')[0]
  const span = months.length === 1 ? first : `${first}–${last}`
  const days = upToDay ? `, over days 1–${upToDay} of each month` : ''
  return `Usual = your average for ${span}${days}.`
}

function ChangeBars({ month, currency }: { month: string; currency: Currency }) {
  const changes = useCategoryChanges(month)
  const compared = changes.data?.compared_months ?? []
  const rows = changes.data?.currencies.find((c) => c.currency === currency)?.changes ?? []
  // Bars are drawn only; every number shown is the API's exact string.
  const max = Math.max(...rows.map((r) => Math.abs(Number(r.change))), 0)

  return (
    <figure className="trend-figure">
      <figcaption className="trend-caption">
        <span>Compared with your usual</span>
      </figcaption>

      {changes.isPending && <p className="muted">Loading…</p>}
      {changes.isError && (
        <p className="error" role="alert">
          {changes.error.message}
        </p>
      )}
      {changes.isSuccess && compared.length === 0 && (
        <p className="muted">
          Nothing to compare with yet: this needs a month of spending before{' '}
          {monthLabel(month)}.
        </p>
      )}
      {compared.length > 0 && (
        <>
          <p className="hint">{usualLabel(compared, changes.data?.up_to_day)}</p>
          {rows.length === 0 ? (
            <p className="muted">No {currency} spending in these months.</p>
          ) : (
            <ul className="ranking changes">
              {rows.map((row) => (
                <ChangeRow key={row.category} row={row} currency={currency} max={max} />
              ))}
            </ul>
          )}
        </>
      )}
    </figure>
  )
}

function ChangeRow({ row, currency, max }: { row: CategoryChange; currency: Currency; max: number }) {
  const change = Number(row.change)
  const size = max > 0 ? `${(Math.abs(change) / max) * 50}%` : '0%'

  return (
    <li>
      <div className="ranking-line">
        <span className="ranking-name">{row.category}</span>
        <span className="ranking-amount">
          {change === 0 ? (
            <span className="muted">same as usual</span>
          ) : (
            <>
              {/* Spending more is the bad direction, so its arrow is red; less is green.
                  Screen readers hear "up" / "down" instead of the arrow. */}
              <span className={change > 0 ? 'change-bad' : 'change-good'}>
                <ChangeArrow up={change > 0} />
              </span>{' '}
              <span className="visually-hidden">{change > 0 ? 'up ' : 'down '}</span>
              {formatMoney(row.change.replace('-', ''), currency)}
            </>
          )}
        </span>
      </div>
      {/* From the middle: right for more than usual, left for less. */}
      <span className="change-track" aria-hidden="true">
        <span className="change-mid" />
        {change !== 0 && (
          <span className={change > 0 ? 'change-bar up' : 'change-bar down'} style={{ width: size }} />
        )}
      </span>
      <span className="hint">
        {formatMoney(row.now, currency)} now · usual {formatMoney(row.usual, currency)}
      </span>
    </li>
  )
}
