import { useId, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { useNavigate } from 'react-router'

import type { Currency } from '../api/client'
import { changePassword, downloadExpenses } from '../api/client'
import { useMe, useUpdateMe } from '../api/hooks'
import { CURRENCIES } from '../api/options'
import { Chevron } from '../components/Icon'
import { RepeatList } from '../components/RepeatList'
import type { Theme } from '../theme'
import { applyTheme, savedTheme } from '../theme'
import { useAuth } from '../useAuth'

/** Your order: Account, Appearance, Your data, Repeating expenses, Help, Log out,
 * and Delete my account last, on its own. */
export function SettingsPage() {
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
      <Account />
      <Appearance />
      <YourData />
      <RepeatList />
      <Help />
      <button type="button" className="secondary" onClick={handleLogOut} disabled={busy}>
        {busy ? 'Logging out…' : 'Log out'}
      </button>
      <DeleteAccount />
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId()
  return (
    <section className="settings-section" aria-labelledby={id}>
      <h2 id={id} className="settings-heading">
        {title}
      </h2>
      <div className="card settings-card">{children}</div>
    </section>
  )
}

// --- Account -----------------------------------------------------------------------

function Account() {
  const me = useMe()
  const update = useUpdateMe()
  const [changingPassword, setChangingPassword] = useState(false)

  return (
    <Section title="Account">
      {me.isPending && <p className="muted">Loading…</p>}
      {me.isError && <p className="error">{me.error.message}</p>}
      {me.data && (
        <>
          <div className="settings-row">
            <span>Email</span>
            <span className="muted settings-value">{me.data.email}</span>
          </div>
          <div className="settings-row">
            <span>
              Default currency
              <span className="hint settings-hint">For new expenses typed without one</span>
            </span>
            <div className="toggle" role="group" aria-label="Default currency">
              {CURRENCIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  className={c === me.data.default_currency ? 'active' : ''}
                  aria-pressed={c === me.data.default_currency}
                  disabled={update.isPending}
                  onClick={() => update.mutate({ default_currency: c as Currency })}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          {update.isError && (
            <p className="error" role="alert">
              {update.error.message}
            </p>
          )}
          <div className="settings-row settings-row-stack">
            <button
              type="button"
              className="settings-link"
              aria-expanded={changingPassword}
              onClick={() => setChangingPassword((o) => !o)}
            >
              Change password <Chevron direction={changingPassword ? 'down' : 'right'} />
            </button>
            {changingPassword && <ChangePassword onDone={() => setChangingPassword(false)} />}
          </div>
        </>
      )}
    </Section>
  )
}

function ChangePassword({ onDone }: { onDone: () => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await changePassword(current, next)
      setDone(true)
      setCurrent('')
      setNext('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change your password')
    } finally {
      setSaving(false)
    }
  }

  if (done) {
    return (
      <p className="settings-done" role="status">
        Password changed. Your other devices have been logged out.{' '}
        <button type="button" className="secondary small" onClick={onDone}>
          Done
        </button>
      </p>
    )
  }

  return (
    <form className="settings-form" onSubmit={submit}>
      <label>
        Current password
        <input
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
      </label>
      <label>
        New password <span className="hint">(at least 8 characters)</span>
        <input
          type="password"
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="card-actions">
        <button type="button" className="secondary" onClick={onDone}>
          Cancel
        </button>
        <button type="submit" disabled={saving || !current || next.length < 8}>
          {saving ? 'Saving…' : 'Change password'}
        </button>
      </div>
    </form>
  )
}

// --- Appearance --------------------------------------------------------------------

const THEMES: { value: Theme; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Match phone' },
]

function Appearance() {
  const [theme, setTheme] = useState<Theme>(savedTheme)

  function choose(value: Theme) {
    applyTheme(value)
    setTheme(value)
  }

  return (
    <Section title="Appearance">
      <div className="toggle toggle-fill" role="group" aria-label="Appearance">
        {THEMES.map((t) => (
          <button
            key={t.value}
            type="button"
            className={t.value === theme ? 'active' : ''}
            aria-pressed={t.value === theme}
            onClick={() => choose(t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>
    </Section>
  )
}

// --- Your data ---------------------------------------------------------------------

function YourData() {
  const [state, setState] = useState<'idle' | 'working' | 'done' | 'failed'>('idle')

  async function exportCsv() {
    setState('working')
    try {
      await downloadExpenses()
      setState('done')
    } catch {
      setState('failed')
    }
  }

  return (
    <Section title="Your data">
      <div className="settings-row">
        <span>
          Export my expenses
          <span className="hint settings-hint">
            A spreadsheet (CSV) of everything you've logged
          </span>
        </span>
        <button
          type="button"
          className="secondary"
          onClick={exportCsv}
          disabled={state === 'working'}
        >
          {state === 'working' ? 'Preparing…' : 'Download'}
        </button>
      </div>
      {state === 'done' && (
        <p className="muted" role="status">
          Downloaded.
        </p>
      )}
      {state === 'failed' && (
        <p className="error" role="alert">
          Couldn't export right now - try again.
        </p>
      )}
    </Section>
  )
}

// --- Help --------------------------------------------------------------------------

function Help() {
  return (
    <Section title="Help">
      {/* <details> opens and closes by itself, and works with keyboards and screen readers. */}
      <details className="settings-help">
        <summary>Example sentences &amp; questions</summary>
        <h3>Adding expenses</h3>
        <ul>
          <li>"4.50 bubble tea yesterday"</li>
          <li>"rm12 nasi lemak and 3 for parking"</li>
          <li>"23.40 tesco last friday"</li>
          <li>Tap the camera to read a receipt photo - check the card before saving.</li>
        </ul>
        <h3>Asking questions (the chat bubble)</h3>
        <ul>
          <li>"How much did I spend yesterday?"</li>
          <li>"How much on food in October vs September?"</li>
          <li>"Where did my money go last month?"</li>
          <li>Ask each question in full - it answers totals by date and category.</li>
        </ul>
      </details>
    </Section>
  )
}

// --- Delete account ----------------------------------------------------------------

function DeleteAccount() {
  const { deleteAccount } = useAuth()
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputId = useId()

  async function confirm() {
    setDeleting(true)
    setError(null)
    try {
      await deleteAccount() // reloads at the start screen
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't delete your account")
      setDeleting(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="secondary small danger-outline danger-link"
        onClick={() => setOpen(true)}
      >
        Delete my account
      </button>
    )
  }

  return (
    <section className="card danger-zone" aria-label="Delete my account">
      <h2>Delete my account</h2>
      <p>
        This permanently deletes your account and everything in it: all expenses, budgets, repeating
        expenses and summaries. It can't be undone.
      </p>
      <p className="muted">Tip: export your expenses first if you want a copy.</p>
      <label htmlFor={inputId}>
        Type <strong>DELETE</strong> to confirm
      </label>
      <input
        id={inputId}
        autoComplete="off"
        autoCapitalize="characters"
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
      />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="card-actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setOpen(false)
            setTyped('')
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          className="danger"
          disabled={typed !== 'DELETE' || deleting}
          onClick={confirm}
        >
          {deleting ? 'Deleting…' : 'Delete my account'}
        </button>
      </div>
    </section>
  )
}
