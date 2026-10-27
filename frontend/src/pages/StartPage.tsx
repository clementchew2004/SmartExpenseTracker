import { Link } from 'react-router'

/** First screen when logged out: two ways in. */
export function StartPage() {
  return (
    <div className="auth-page">
      <h1>Smart Expense Tracker</h1>
      <p className="muted">Log spending in plain English and see where it goes.</p>
      <div className="auth-choices">
        <Link className="button" to="/login">
          Log in
        </Link>
        <Link className="button secondary" to="/register">
          Register an account
        </Link>
      </div>
    </div>
  )
}
