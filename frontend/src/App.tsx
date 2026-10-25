import './App.css'
import { MonthlyChart } from './components/MonthlyChart'
import { QuickAdd } from './components/QuickAdd'

function App() {
  return (
    <main className="app">
      <h1>Add expense</h1>
      <QuickAdd />
      <MonthlyChart />
    </main>
  )
}

export default App
