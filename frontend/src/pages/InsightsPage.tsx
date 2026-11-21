import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { ErrorBoundary } from '../components/ErrorBoundary'
import { TrendCharts } from '../components/TrendCharts'
import { isMonthKey, monthKey } from '../dates'
import { BudgetPage } from './BudgetPage'

/** The Insights tab: your budget first, then the graphs for the six months
 * ending at the month its arrows show. The question chat lives in the chat
 * bubble, which shows on this page too. */
export function InsightsPage() {
  const [params] = useSearchParams()
  // Read the clock once when the page opens (keeps render pure).
  const [thisMonth] = useState(() => monthKey(new Date()))
  const month = isMonthKey(params.get('month')) ? params.get('month')! : thisMonth

  return (
    <>
      <h1>How you're doing</h1>
      <ErrorBoundary name="budget">
        <BudgetPage />
      </ErrorBoundary>
      <ErrorBoundary name="graphs">
        <TrendCharts month={month} />
      </ErrorBoundary>
    </>
  )
}
