import { AskChat } from '../components/AskChat'
import { ErrorBoundary } from '../components/ErrorBoundary'
import type { AskChat as Chat } from '../useAskChat'
import { BudgetPage } from './BudgetPage'

/** The Insights tab (was Budget): ask questions first, then your budget. */
export function InsightsPage({ chat }: { chat: Chat }) {
  return (
    <>
      <h1>Insights</h1>
      {/* Separate boundaries: if one part crashes, the other keeps working. */}
      <ErrorBoundary name="question chat">
        <AskChat chat={chat} />
      </ErrorBoundary>
      <ErrorBoundary name="budget">
        <BudgetPage />
      </ErrorBoundary>
    </>
  )
}
