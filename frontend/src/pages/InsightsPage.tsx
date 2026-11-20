import { ErrorBoundary } from '../components/ErrorBoundary'
import { BudgetPage } from './BudgetPage'

/** The Insights tab: your budget first; graphs come below it. The question
 * chat moved into the chat bubble, which shows on this page too. */
export function InsightsPage() {
  return (
    <>
      <h1>Insights</h1>
      <ErrorBoundary name="budget">
        <BudgetPage />
      </ErrorBoundary>
    </>
  )
}
