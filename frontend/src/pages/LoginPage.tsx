import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation } from 'react-router'

import { useAuth } from '../useAuth'

/** Set by the register page, so you only have to type the password. */
export type LoginState = { email?: string; justRegistered?: boolean }

export function LoginPage() {
  const { logIn } = useAuth()
  const state = (useLocation().state ?? {}) as LoginState
  const [email, setEmail] = useState(state.email ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      // On success the app switches to the logged-in screens by itself.
      await logIn(email, password)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <form className="auth-page" onSubmit={handleSubmit}>
      <h1>Log in</h1>
      {state.justRegistered && (
        <p className="notice" role="status">
          Account created - log in
        </p>
      )}
      <label>
        Email
        <input
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          required
          autoFocus={Boolean(state.email)}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? 'Logging in…' : 'Log in'}
      </button>
      <p className="muted">
        No account yet? <Link to="/register">Register an account</Link>
      </p>
    </form>
  )
}
