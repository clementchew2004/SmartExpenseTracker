import { useState } from 'react'

import './App.css'
import type { Currency } from './api/client'
import { ErrorBoundary } from './components/ErrorBoundary'
import { MonthlyChart } from './components/MonthlyChart'
import { QuickAdd } from './components/QuickAdd'

function App() {
  // Shared so the chart can jump to the currency you just saved in.
  const [chartCurrency, setChartCurrency] = useState<Currency>('GBP')

  return (
    <main className="app">
      <h1>Add expense</h1>
      {/* Separate boundaries: if one part crashes, the other keeps working. */}
      <ErrorBoundary name="quick-add form">
        <QuickAdd onSaved={setChartCurrency} />
      </ErrorBoundary>
      <ErrorBoundary name="monthly chart">
        <MonthlyChart currency={chartCurrency} onCurrencyChange={setChartCurrency} />
      </ErrorBoundary>
    </main>
  )
}

export default App
