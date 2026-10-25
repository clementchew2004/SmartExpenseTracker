import { useState } from 'react'

import './App.css'
import type { Currency } from './api/client'
import { MonthlyChart } from './components/MonthlyChart'
import { QuickAdd } from './components/QuickAdd'

function App() {
  // Shared so the chart can jump to the currency you just saved in.
  const [chartCurrency, setChartCurrency] = useState<Currency>('GBP')

  return (
    <main className="app">
      <h1>Add expense</h1>
      <QuickAdd onSaved={setChartCurrency} />
      <MonthlyChart currency={chartCurrency} onCurrencyChange={setChartCurrency} />
    </main>
  )
}

export default App
