import type { Category, Currency } from '../api/client'
import { formatMoney } from '../api/options'

export type RankingRow = {
  category: Category
  amount: string // exact string from the API, for display
  previous?: string // the comparison period's amount, if any
}

/**
 * Spending by category as a ranked list: biggest first, the name and amount on
 * one line and a thin 2px bar under it at its true share of the biggest. The top
 * row's bar is ink, the rest grey (so "most costly first" is seen, not only
 * read). With `previous`, a grey tick on each bar marks last period's amount.
 *
 * Replaces the colourful donut and stacked bars: the category names carry the
 * meaning, so no rainbow of colours is needed (Achromatic ledger style).
 */
export function CategoryRanking({
  rows,
  currency,
  previousLabel,
  colours,
}: {
  rows: RankingRow[]
  currency: Currency
  previousLabel?: string
  /** As the legend of a chart: a colour dot per row, and no bars (the chart
   * already shows each share). */
  colours?: Record<Category, string>
}) {
  const sorted = [...rows].sort((a, b) => Number(b.amount) - Number(a.amount))
  // Bars are drawn only: every number on screen is the API's exact string.
  const max = Math.max(...sorted.flatMap((r) => [Number(r.amount), Number(r.previous ?? 0)]), 0)
  const share = (value: string | undefined) =>
    max > 0 ? `${(Number(value ?? 0) / max) * 100}%` : '0%'

  return (
    <ul className="ranking">
      {sorted.map((row, i) => (
        <li key={row.category}>
          <div className="ranking-line">
            <span className="ranking-name">
              {colours && (
                <span className="ranking-dot" style={{ background: colours[row.category] }} />
              )}
              {row.category}
            </span>
            {/* Last period beside this one, in grey, on the same line and right edge. */}
            {row.previous !== undefined && previousLabel && (
              <span className="ranking-previous">
                {previousLabel} {formatMoney(row.previous, currency)}
              </span>
            )}
            <span className="ranking-amount">{formatMoney(row.amount, currency)}</span>
          </div>
          {!colours && (
            <span className="ranking-track" aria-hidden="true">
              <span
                className={i === 0 ? 'ranking-bar ranking-bar-top' : 'ranking-bar'}
                style={{ width: share(row.amount) }}
              />
              {row.previous !== undefined && Number(row.previous) > 0 && (
                <span className="ranking-tick" style={{ left: share(row.previous) }} />
              )}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}
