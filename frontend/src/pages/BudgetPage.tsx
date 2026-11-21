import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import type { BudgetStatus, Currency, MonthBudgets, Outlook } from '../api/client'
import {
  useBudgets,
  useDeleteDefaultBudget,
  useSetDefaultBudget,
  useSetMonthBudget,
} from '../api/hooks'
import { CURRENCIES, CURRENCY_SYMBOL, formatMoney } from '../api/options'
import { isMonthKey, monthKey, monthLabel, shiftMonth } from '../dates'

// Your wording. Before day 14 there's no sentence: the bar says enough.
const VERDICT: Record<Outlook, string | null> = {
  too_early: null,
  on_track: 'Expected to spend within budget',
  likely_over: "You're likely to overspend your budget",
  over: "You've exceeded your budget",
  under: 'You stayed within budget',
  upcoming: 'Planned',
}

// Bar colour per outlook: green within budget, yellow likely over, red over.
// The verdict text is always shown too, so colour is never the only signal.
const TONE: Record<Outlook, string> = {
  too_early: 'tone-ok',
  on_track: 'tone-ok',
  under: 'tone-ok',
  likely_over: 'tone-warn',
  over: 'tone-over',
  upcoming: 'tone-planned',
}

/** Your budget, on the Insights tab under the questions: one month's budgets
 * per currency, with month arrows. */
export function BudgetPage() {
  const [params, setParams] = useSearchParams()
  // Read the clock once when the page opens (keeps render pure).
  const [thisMonth] = useState(() => monthKey(new Date()))
  const month = isMonthKey(params.get('month')) ? params.get('month')! : thisMonth
  const budgets = useBudgets(month)

  if (budgets.isPending) return <p className="muted">Loading…</p>
  if (budgets.isError) return <p className="error">{budgets.error.message}</p>

  const data = budgets.data
  if (Object.keys(data.defaults).length === 0 && data.budgets.length === 0) {
    return <FirstSetup month={thisMonth} />
  }

  function go(by: number) {
    setParams({ month: shiftMonth(month, by) }, { replace: true })
  }

  // The month prompt: this month, and a currency still on your usual amount.
  const needsPrompt =
    month === thisMonth ? data.budgets.filter((b) => b.source === 'default') : []

  return (
    <section className="budget" aria-label="Budget">
      <div className="month-nav">
        <button
          type="button"
          className="secondary icon-button"
          aria-label={`Previous month, ${monthLabel(shiftMonth(month, -1))}`}
          onClick={() => go(-1)}
        >
          ‹
        </button>
        <h2 className="month-title">{monthLabel(month)}</h2>
        <button
          type="button"
          className="secondary icon-button"
          aria-label={`Next month, ${monthLabel(shiftMonth(month, 1))}`}
          onClick={() => go(1)}
        >
          ›
        </button>
      </div>

      {needsPrompt.map((b) => (
        <MonthPrompt key={b.currency} month={month} budget={b} />
      ))}

      {data.budgets.length === 0 ? (
        <p className="empty">No budget for {monthLabel(month)}.</p>
      ) : (
        data.budgets.map((b) => (
          <BudgetCard key={b.currency} month={month} budget={b} canChange={month >= thisMonth} />
        ))
      )}

      <UsualBudgets defaults={data.defaults} />
    </section>
  )
}

/** First visit: nothing set yet. Saves your usual amounts AND this month's. */
function FirstSetup({ month }: { month: string }) {
  const [gbp, setGbp] = useState('')
  const [myr, setMyr] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const setDefault = useSetDefaultBudget()
  const setMonth = useSetMonthBudget()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const amounts: [Currency, string][] = [['GBP', gbp]]
      if (myr.trim()) amounts.push(['MYR', myr])
      for (const [currency, amount] of amounts) {
        await setDefault.mutateAsync({ currency, amount: amount.trim() })
        // You've just typed this month's amount, so the month prompt needn't ask again.
        await setMonth.mutateAsync({ month, currency, amount: amount.trim() })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <form className="auth-page budget-setup" onSubmit={handleSubmit}>
      <h2>Set your monthly budget</h2>
      <p className="muted">
        This is your usual amount. Each month you can keep it or set a different one.
      </p>
      <label>
        GBP (£)
        <input
          inputMode="decimal"
          required
          placeholder="800"
          value={gbp}
          onChange={(e) => setGbp(e.target.value)}
        />
      </label>
      <label>
        MYR (RM) <span className="hint">(optional)</span>
        <input inputMode="decimal" placeholder="500" value={myr} onChange={(e) => setMyr(e.target.value)} />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? 'Saving…' : 'Save budget'}
      </button>
    </form>
  )
}

/** "Set your budget for November": shown until you type this month's amount. */
function MonthPrompt({ month, budget }: { month: string; budget: BudgetStatus }) {
  const setMonth = useSetMonthBudget()
  return (
    <div className="card budget-prompt">
      <h2>
        Set your {budget.currency} budget for {monthLabel(month)}
      </h2>
      <AmountForm
        currency={budget.currency}
        // Pre-filled with your usual amount: keeping it is one tap on Save.
        initial={budget.amount}
        submitLabel="Save"
        onSubmit={(amount) => setMonth.mutateAsync({ month, currency: budget.currency, amount })}
      />
    </div>
  )
}

/** One currency: "£620 of £800", the coloured bar, your verdict, and Change. */
function BudgetCard({
  month,
  budget,
  canChange,
}: {
  month: string
  budget: BudgetStatus
  canChange: boolean
}) {
  const [changing, setChanging] = useState(false)
  const setMonth = useSetMonthBudget()
  const verdict = VERDICT[budget.outlook]
  const spent = formatMoney(budget.spent, budget.currency)
  const total = formatMoney(budget.amount, budget.currency)
  // Only for drawing the bar's width - money maths stays on the server, in Decimal.
  const fill = Math.min(Number(budget.spent) / Number(budget.amount), 1) * 100

  return (
    <div className="card budget-card">
      <div className="budget-numbers">
        <span>
          <strong>{spent}</strong> of {total}
        </span>
        {budget.source === 'default' && <span className="hint">usual amount</span>}
      </div>
      <div className={`budget-bar ${TONE[budget.outlook]}`} role="img" aria-label={`${spent} of ${total} spent`}>
        <div className="budget-fill" style={{ width: `${fill}%` }} />
      </div>
      {verdict && <p className={`budget-verdict ${TONE[budget.outlook]}`}>{verdict}</p>}

      {canChange &&
        (changing ? (
          <AmountForm
            currency={budget.currency}
            initial={budget.amount}
            submitLabel="Save"
            onCancel={() => setChanging(false)}
            onSubmit={async (amount) => {
              await setMonth.mutateAsync({ month, currency: budget.currency, amount })
              setChanging(false)
            }}
          />
        ) : (
          <button type="button" className="secondary small" onClick={() => setChanging(true)}>
            Change {monthLabel(month)} budget
          </button>
        ))}
    </div>
  )
}

/** Your usual amounts: used for any month you don't set yourself. */
function UsualBudgets({ defaults }: { defaults: MonthBudgets['defaults'] }) {
  const [editing, setEditing] = useState<Currency | null>(null)
  const setDefault = useSetDefaultBudget()
  const remove = useDeleteDefaultBudget()

  return (
    <div className="usual-budgets">
      <h2>Usual monthly budget</h2>
      <ul>
        {CURRENCIES.map((currency) => {
          const amount = defaults[currency]
          return (
            <li key={currency}>
              {editing === currency ? (
                <AmountForm
                  currency={currency}
                  initial={amount ?? ''}
                  submitLabel="Save"
                  onCancel={() => setEditing(null)}
                  onSubmit={async (value) => {
                    await setDefault.mutateAsync({ currency, amount: value })
                    setEditing(null)
                  }}
                />
              ) : (
                <>
                  <span>
                    {currency}: {amount ? formatMoney(amount, currency) : <span className="muted">not set</span>}
                  </span>
                  <span className="usual-actions">
                    <button
                      type="button"
                      className="secondary small"
                      onClick={() => setEditing(currency)}
                    >
                      {amount ? 'Edit' : 'Set'}
                    </button>
                    {amount && (
                      <button
                        type="button"
                        className="secondary small"
                        onClick={() => remove.mutate(currency)}
                      >
                        Remove
                      </button>
                    )}
                  </span>
                </>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** An amount box with Save (and optional Cancel). The server checks the amount. */
function AmountForm({
  currency,
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  currency: Currency
  initial: string
  submitLabel: string
  onSubmit: (amount: string) => Promise<unknown>
  onCancel?: () => void
}) {
  const [amount, setAmount] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const inputId = useId() // unique even when two GBP forms are open at once

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSubmit(amount.trim())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="amount-form" onSubmit={handleSubmit}>
      <div className="input-row">
        <label className="visually-hidden" htmlFor={inputId}>
          Amount in {currency}
        </label>
        <span className="amount-symbol" aria-hidden="true">
          {CURRENCY_SYMBOL[currency]}
        </span>
        <input
          id={inputId}
          inputMode="decimal"
          required
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <button type="submit" disabled={busy}>
          {busy ? 'Saving…' : submitLabel}
        </button>
      </div>
      {onCancel && (
        <button type="button" className="secondary small" onClick={onCancel}>
          Cancel
        </button>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
