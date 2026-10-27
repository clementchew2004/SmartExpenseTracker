import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { login, logout, refreshAccessToken, setOnSessionEnded } from './api/client'
import type { AuthStatus } from './useAuth'
import { AuthContext } from './useAuth'

/** Knows whether you're logged in, and lets any screen log in or out. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('checking')
  const queryClient = useQueryClient()

  useEffect(() => {
    // A request found the session over (30 days up, or logged out elsewhere).
    // Drop the cached data too, so the next person on this phone never sees it.
    setOnSessionEnded(() => {
      queryClient.clear()
      setStatus('out')
    })

    // After a reload the access token is gone, but the cookie may not be.
    // StrictMode runs this effect twice in development; both calls share the
    // one refresh in progress, so the server still sees a single request.
    let current = true
    refreshAccessToken().then(
      (loggedIn) => current && setStatus(loggedIn ? 'in' : 'out'),
      () => current && setStatus('out'), // server unreachable: the login form will say so
    )
    return () => {
      current = false
    }
  }, [queryClient])

  async function logIn(email: string, password: string) {
    await login(email, password)
    setStatus('in')
  }

  async function logOut() {
    try {
      await logout()
    } finally {
      queryClient.clear()
      setStatus('out')
    }
  }

  return <AuthContext value={{ status, logIn, logOut }}>{children}</AuthContext>
}
