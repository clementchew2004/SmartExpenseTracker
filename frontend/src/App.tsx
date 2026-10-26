import { useState } from 'react'
import { Route, Routes } from 'react-router'

import './App.css'
import type { Currency } from './api/client'
import { formatMoney } from './api/options'
import { ErrorBoundary } from './components/ErrorBoundary'
import { MonthlyChart } from './components/MonthlyChart'
import { QuickAdd } from './components/QuickAdd'
import { TabBar } from './components/TabBar'
import { EditExpensePage } from './pages/EditExpensePage'
import { ExpensesPage } from './pages/ExpensesPage'
import { useDelayedDelete } from './useDelayedDelete'

function App() {
  // Shared so the chart can jump to the currency you just saved in.
  const [chartCurrency, setChartCurrency] = useState<Currency>('GBP')
  // Lives here, above the pages, so the Undo bar survives edit page -> list.
  const deletion = useDelayedDelete()

  return (
    <>
      <main className="app">
        <Routes>
          <Route
            path="/"
            element={
              <>
                <h1>Add expense</h1>
                {/* Separate boundaries: if one part crashes, the other keeps working. */}
                <ErrorBoundary name="quick-add form">
                  <QuickAdd onSaved={setChartCurrency} />
                </ErrorBoundary>
                <ErrorBoundary name="monthly chart">
                  <MonthlyChart currency={chartCurrency} onCurrencyChange={setChartCurrency} />
                </ErrorBoundary>
              </>
            }
          />
          <Route
            path="/expenses"
            element={
              <ErrorBoundary name="expense list">
                <ExpensesPage hiddenId={deletion.pending?.id ?? null} />
              </ErrorBoundary>
            }
          />
          <Route
            path="/expenses/:id"
            element={
              <ErrorBoundary name="expense editor">
                <EditExpensePage onDelete={deletion.schedule} />
              </ErrorBoundary>
            }
          />
        </Routes>
      </main>

      {deletion.pending && (
        <div className="notice undo-bar" role="status">
          <span>
            Deleted {deletion.pending.merchant}{' '}
            {formatMoney(deletion.pending.amount, deletion.pending.currency)}
          </span>
          <button type="button" className="link" onClick={deletion.undo}>
            Undo
          </button>
        </div>
      )}
      {deletion.error && (
        <p className="error undo-bar" role="alert">
          Couldn't delete: {deletion.error.message}
        </p>
      )}

      <TabBar />
    </>
  )
}

export default App
