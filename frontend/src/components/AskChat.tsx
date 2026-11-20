import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { Currency } from '../api/client'
import { formatMoney } from '../api/options'
import { dateRange, shortMonthLabel } from '../dates'
import type { AskChat as Chat, ChatTurn } from '../useAskChat'

const EXAMPLES = [
  'How much did I spend yesterday?',
  'How much did I spend eating out last month?',
  'Food this month vs last month?',
  'Where did my money go last month?',
]

/** The mini chatbot, inside the chat bubble's window. Each question is answered on its own. */
export function AskChat({ chat, autoFocus = false }: { chat: Chat; autoFocus?: boolean }) {
  const [question, setQuestion] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const waiting = chat.turns.some((t) => t.status === 'waiting')

  // Keep the newest reply in view as the chat grows.
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [chat.turns])

  function submit(event: FormEvent) {
    event.preventDefault()
    const text = question.trim()
    if (!text || waiting) return
    chat.ask(text)
    setQuestion('')
  }

  return (
    <section className="ask" aria-label="Ask about your spending">
      <h2>Ask about your spending</h2>

      {chat.turns.length === 0 ? (
        <div className="ask-intro">
          <ul className="ask-examples" aria-label="Example questions">
            {EXAMPLES.map((example) => (
              <li key={example}>
                <button type="button" className="secondary chip" onClick={() => chat.ask(example)}>
                  {example}
                </button>
              </li>
            ))}
          </ul>
          <p className="muted hint">
            Totals, breakdowns and comparisons by date and category - not single shops or expenses.
            Ask each question in full.
          </p>
        </div>
      ) : (
        // aria-live: screen readers hear each new reply once it settles.
        <div className="ask-log" aria-live="polite">
          {chat.turns.map((turn) => (
            <Turn key={turn.id} turn={turn} chat={chat} />
          ))}
          <div ref={end} />
        </div>
      )}

      <form className="input-row" onSubmit={submit}>
        <label htmlFor="ask-question" className="visually-hidden">
          Your question
        </label>
        <input
          id="ask-question"
          autoComplete="off"
          autoFocus={autoFocus}
          placeholder="How much on food in October?"
          value={question}
          maxLength={300}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={!question.trim() || waiting}>
          Ask
        </button>
      </form>

      {chat.turns.length > 0 && (
        <button type="button" className="link ask-clear" onClick={chat.clear} disabled={waiting}>
          Clear chat
        </button>
      )}
    </section>
  )
}

function Turn({ turn, chat }: { turn: ChatTurn; chat: Chat }) {
  return (
    <>
      <p className="bubble bubble-you">{turn.question}</p>
      <div className="bubble bubble-reply">
        <Reply turn={turn} chat={chat} />
      </div>
    </>
  )
}

function Reply({ turn, chat }: { turn: ChatTurn; chat: Chat }) {
  if (turn.status === 'waiting') return <Typing />
  if (turn.status === 'failed' || !turn.reply) {
    return (
      <p>
        Couldn't answer right now.{' '}
        <button type="button" className="link" onClick={() => chat.retry(turn)}>
          Try again
        </button>
      </p>
    )
  }

  const { answer, needs_currency, facts } = turn.reply
  if (needs_currency) {
    // Your choice: just the buttons. The question right above is the context.
    return (
      <div className="currency-choice" role="group" aria-label="Which currency?">
        {needs_currency.map((c) => (
          <button
            key={c}
            type="button"
            className="secondary"
            onClick={() => chat.chooseCurrency(turn, c as Currency)}
          >
            {c}
          </button>
        ))}
      </div>
    )
  }

  return (
    <>
      <p>{answer ?? "Couldn't word an answer - here are the numbers."}</p>
      {facts.length > 0 && (
        <ul className="ask-facts">
          {facts.map((fact, i) => (
            <Fact key={i} fact={fact as Fact} />
          ))}
        </ul>
      )}
    </>
  )
}

/** Three dots while the AI works; a note if it's taking a while. */
function Typing() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 5000)
    return () => clearTimeout(timer)
  }, [])
  return (
    <>
      <p className="visually-hidden" role="status">
        Working out your answer
      </p>
      <span className="typing" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {slow && <p className="muted waiting-note">Still working…</p>}
    </>
  )
}

// The tool results as the API sends them. Every number shown comes from here,
// worked out by code - never from the AI's sentence.
type Range = { from: string; to: string; total: string }
type Fact =
  | ({ tool: 'get_total'; category: string | null; currency: Currency } & Range)
  | {
      tool: 'get_breakdown'
      from: string
      to: string
      group_by: 'category' | 'month'
      currency: Currency
      rows: { label: string; total: string }[]
    }
  | {
      tool: 'compare'
      category: string | null
      currency: Currency
      a: Range
      b: Range
      difference_a_minus_b: string
      change_pct_a_vs_b: number | null
    }

/** Your format: "Food · 1–31 Oct · £142.30". */
function Fact({ fact }: { fact: Fact }) {
  const money = (amount: string) => formatMoney(amount, fact.currency)

  if (fact.tool === 'get_total') {
    return (
      <li>
        {fact.category ?? 'All spending'} · {dateRange(fact.from, fact.to)} ·{' '}
        <strong>{money(fact.total)}</strong>
      </li>
    )
  }
  if (fact.tool === 'get_breakdown') {
    return (
      <li>
        {dateRange(fact.from, fact.to)}
        <ul>
          {fact.rows.length === 0 && <li className="muted">Nothing spent</li>}
          {fact.rows.map((row) => (
            <li key={row.label}>
              {fact.group_by === 'month' ? shortMonthLabel(row.label) : row.label} ·{' '}
              <strong>{money(row.total)}</strong>
            </li>
          ))}
        </ul>
      </li>
    )
  }
  const diff = Number(fact.difference_a_minus_b)
  return (
    <li>
      {fact.category ?? 'All spending'} · {dateRange(fact.a.from, fact.a.to)}{' '}
      <strong>{money(fact.a.total)}</strong> vs {dateRange(fact.b.from, fact.b.to)}{' '}
      <strong>{money(fact.b.total)}</strong>
      {diff !== 0 && (
        <>
          {' '}
          · <span aria-hidden="true">{diff > 0 ? '▲' : '▼'} </span>
          <span className="visually-hidden">{diff > 0 ? 'up ' : 'down '}</span>
          {money(fact.difference_a_minus_b.replace('-', ''))}
          {fact.change_pct_a_vs_b != null && ` (${Math.abs(fact.change_pct_a_vs_b)}%)`}
        </>
      )}
    </li>
  )
}
