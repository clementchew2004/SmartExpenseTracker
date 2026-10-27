import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import type { Currency } from '../api/client'
import { register } from '../api/client'
import type { LoginState } from './LoginPage'

export function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [currency, setCurrency] = useState<Currency>('GBP')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register({ email, password, invite_code: inviteCode, default_currency: currency })
      // Your decision: go to the login page, with the email already filled in.
      const state: LoginState = { email, justRegistered: true }
      navigate('/login', { state })
    } catch (e) {
      // The server's own words, e.g. "That invite code isn't valid - ask for a new one".
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <form className="auth-page" onSubmit={handleSubmit}>
      <h1>Register an account</h1>
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
        Password <span className="hint">(at least 8 characters)</span>
        <input
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <label>
        Invite code
        <input
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          required
          placeholder="ABCD-2345"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
        />
      </label>
      <label>
        Default currency <span className="hint">(used when you don't say £ or RM)</span>
        <select value={currency} onChange={(e) => setCurrency(e.target.value as Currency)}>
          <option value="GBP">GBP (£)</option>
          <option value="MYR">MYR (RM)</option>
        </select>
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? 'Creating account…' : 'Register'}
      </button>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </form>
  )
}
