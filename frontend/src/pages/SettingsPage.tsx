import { useState } from 'react'
import { useNavigate } from 'react-router'

import { useMe } from '../api/hooks'
import { RepeatList } from '../components/RepeatList'
import { useAuth } from '../useAuth'

export function SettingsPage() {
  const me = useMe()
  const { logOut } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  async function handleLogOut() {
    setBusy(true)
    await logOut()
    navigate('/login') // your decision: log out -> login page
  }

  return (
    <div className="settings">
      <h1>Settings</h1>
      {me.isPending && <p className="muted">Loading…</p>}
      {me.isError && <p className="error">{me.error.message}</p>}
      {me.data && (
        <dl className="card account">
          <div>
            <dt>Email</dt>
            <dd>{me.data.email}</dd>
          </div>
          <div>
            <dt>Default currency</dt>
            <dd>{me.data.default_currency}</dd>
          </div>
        </dl>
      )}
      <RepeatList />
      <button type="button" className="secondary" onClick={handleLogOut} disabled={busy}>
        {busy ? 'Logging out…' : 'Log out'}
      </button>
    </div>
  )
}
