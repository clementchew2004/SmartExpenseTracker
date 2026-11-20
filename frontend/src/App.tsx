import { useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router'

import './App.css'
import type { Currency } from './api/client'
import { formatMoney } from './api/options'
import { showsChatBubble } from './chatBubblePages'
import { ChatBubble } from './components/ChatBubble'
import { ErrorBoundary } from './components/ErrorBoundary'
import { MonthlyChart } from './components/MonthlyChart'
import { QuickAdd } from './components/QuickAdd'
import { Reminders } from './components/Reminders'
import { TabBar } from './components/TabBar'
import { WeeklySummaries } from './components/WeeklySummaries'
import { useAuth } from './useAuth'
import { EditExpensePage } from './pages/EditExpensePage'
import { ExpensesPage } from './pages/ExpensesPage'
import { InsightsPage } from './pages/InsightsPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { SettingsPage } from './pages/SettingsPage'
import { StartPage } from './pages/StartPage'
import { useAskChat } from './useAskChat'
import { useDelayedDelete } from './useDelayedDelete'

function App() {
  const { status } = useAuth()

  if (status === 'checking') {
    // Waiting for /auth/refresh after a (re)load. Without this, the login screen
    // would flash for a moment every time before your expenses appear.
    return (
      <main className="app app-loading">
        <div className="spinner" role="status" aria-label="Loading" />
      </main>
    )
  }

  if (status === 'out') {
    return (
      <main className="app">
        <Routes>
          <Route path="/" element={<StartPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          {/* Any app page while logged out (e.g. the session ended) -> log in. */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </main>
    )
  }

  return <LoggedInApp />
}

function LoggedInApp() {
  // Shared so the chart can jump to the currency you just saved in.
  const [chartCurrency, setChartCurrency] = useState<Currency>('GBP')
  // Lives here, above the pages, so the Undo bar survives edit page -> list.
  const deletion = useDelayedDelete()
  // Also up here, so the question chat survives switching tabs.
  const chat = useAskChat()
  const { pathname } = useLocation()
  const bubble = showsChatBubble(pathname)

  return (
    <>
      {/* has-chat-bubble: extra room at the bottom so nothing hides under it. */}
      <main className={bubble ? 'app has-chat-bubble' : 'app'}>
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
                {/* Your choice: reminder cards below the chart. */}
                <ErrorBoundary name="reminders">
                  <Reminders />
                </ErrorBoundary>
                {/* Your choice: weekly summaries at the very bottom, following the chart's currency. */}
                <ErrorBoundary name="weekly summaries">
                  <WeeklySummaries currency={chartCurrency} />
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
          <Route path="/insights" element={<InsightsPage />} />
          {/* The tab's old address (and any ?month= on it) still works. */}
          <Route path="/budget" element={<RenamedTo path="/insights" />} />
          <Route
            path="/settings"
            element={
              <ErrorBoundary name="settings">
                <SettingsPage />
              </ErrorBoundary>
            }
          />
          {/* e.g. /login right after logging in -> the Add screen. */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {deletion.pending && (
        <div className={`notice undo-bar${bubble ? ' beside-bubble' : ''}`} role="status">
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
        <p className={`error undo-bar${bubble ? ' beside-bubble' : ''}`} role="alert">
          Couldn't delete: {deletion.error.message}
        </p>
      )}

      <TabBar />
      {bubble && (
        <ErrorBoundary name="chat">
          <ChatBubble chat={chat} />
        </ErrorBoundary>
      )}
    </>
  )
}

function RenamedTo({ path }: { path: string }) {
  const { search } = useLocation()
  return <Navigate to={{ pathname: path, search }} replace />
}

export default App
