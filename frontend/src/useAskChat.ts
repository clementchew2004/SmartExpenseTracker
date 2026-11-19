import { useState } from 'react'

import type { AskResponse, Currency } from './api/client'
import { askQuestion } from './api/client'

/** One question and its reply. The server forgets every question, so this
 * list - the whole "chat" - lives only here in the browser. */
export type ChatTurn = {
  id: number
  question: string
  currency?: Currency // set once you tapped GBP or MYR
  status: 'waiting' | 'done' | 'failed'
  reply?: AskResponse
}

let nextId = 0

/**
 * The question chat's memory. Used in App, above the pages, so switching tabs
 * keeps the conversation; a reload or logging out clears it.
 *
 * Each question is answered on its own (your choice): nothing earlier is sent.
 */
export function useAskChat() {
  const [turns, setTurns] = useState<ChatTurn[]>([])

  function update(id: number, changes: Partial<ChatTurn>) {
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...changes } : t)))
  }

  async function send(id: number, question: string, currency?: Currency) {
    update(id, { status: 'waiting', currency, reply: undefined })
    try {
      update(id, { status: 'done', reply: await askQuestion(question, currency) })
    } catch {
      update(id, { status: 'failed' })
    }
  }

  return {
    turns,
    ask(question: string) {
      const id = ++nextId
      setTurns((all) => [...all, { id, question, status: 'waiting' }])
      void send(id, question)
    },
    /** "Which currency?" answered: the same question again, with it set. */
    chooseCurrency(turn: ChatTurn, currency: Currency) {
      void send(turn.id, turn.question, currency)
    },
    retry(turn: ChatTurn) {
      void send(turn.id, turn.question, turn.currency)
    },
    clear() {
      setTurns([])
    },
  }
}

export type AskChat = ReturnType<typeof useAskChat>
