// Month and day helpers. Dates from the API are "YYYY-MM-DD" strings; we build Date
// objects in LOCAL time (new Date(y, m, d)) - new Date("2026-10-25") would mean UTC
// midnight and can show the previous day in some timezones.

const MONTH_LABEL = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })
const DAY_LABEL = new Intl.DateTimeFormat('en-GB', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
})

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** "2026-10" for a date. */
export function monthKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`
}

/** True for a well-formed "YYYY-MM". */
export function isMonthKey(value: string | null): value is string {
  return value !== null && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)
}

function firstDay(key: string): Date {
  const [year, month] = key.split('-').map(Number)
  return new Date(year, month - 1, 1)
}

/** The month before (-1) or after (+1); Date handles the year rollover. */
export function shiftMonth(key: string, by: number): string {
  const first = firstDay(key)
  return monthKey(new Date(first.getFullYear(), first.getMonth() + by, 1))
}

/** First and last day of the month, as the API's from/to filter values. */
export function monthBounds(key: string): { from: string; to: string } {
  const first = firstDay(key)
  // Day 0 of next month is the last day of this month.
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0)
  return { from: `${key}-01`, to: `${key}-${pad(last.getDate())}` }
}

/** "October 2026" */
export function monthLabel(key: string): string {
  return MONTH_LABEL.format(firstDay(key))
}

/** "Sun 25 Oct" for "2026-10-25" */
export function dayLabel(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return DAY_LABEL.format(new Date(year, month - 1, day))
}

const SHORT_DAY = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })

function localDate(isoDate: string): Date {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day)
}

/** "9–15 Nov", or "26 Oct – 1 Nov" across two months. */
export function weekLabel(start: string, end: string): string {
  return SHORT_DAY.formatRange(localDate(start), localDate(end))
}
