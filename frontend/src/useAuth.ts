import { createContext, useContext } from 'react'

/** 'checking' = on the way to /auth/refresh after a (re)load; we don't know yet. */
export type AuthStatus = 'checking' | 'in' | 'out'

export type Auth = {
  status: AuthStatus
  logIn: (email: string, password: string) => Promise<void>
  logOut: () => Promise<void>
}

// Filled in by <AuthProvider> (auth.tsx).
export const AuthContext = createContext<Auth | null>(null)

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth must be used inside <AuthProvider>')
  return auth
}
