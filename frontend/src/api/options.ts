import type { Category, Currency } from './client'

// Runtime lists for dropdowns. `satisfies` makes TypeScript check every entry
// against the generated types, so a typo like "Fod" fails the build.
export const CURRENCIES = ['GBP', 'MYR'] as const satisfies readonly Currency[]

export const CATEGORIES = [
  'Food',
  'Groceries',
  'Transport',
  'Shopping',
  'Subscriptions',
  'Entertainment',
  'Bills',
  'Health',
  'Travel',
  'Other',
] as const satisfies readonly Category[]

export const CURRENCY_SYMBOL: Record<Currency, string> = { GBP: '£', MYR: 'RM' }

/** Show a money string from the API as e.g. "£4.50" or "RM 12.00". No float maths. */
export function formatMoney(amount: string, currency: Currency): string {
  return currency === 'GBP' ? `£${amount}` : `RM ${amount}`
}
