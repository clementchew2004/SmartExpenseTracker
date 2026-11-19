import { NavLink } from 'react-router'

/** Bottom navigation. */
export function TabBar() {
  return (
    <nav className="tab-bar" aria-label="Main">
      {/* NavLink adds aria-current="page" to the active tab; CSS highlights it. */}
      <NavLink to="/" end>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add
      </NavLink>
      <NavLink to="/expenses">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
        </svg>
        Expenses
      </NavLink>
      <NavLink to="/insights">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="8" />
          <path d="M12 12l4-4" />
        </svg>
        Insights
      </NavLink>
      <NavLink to="/settings">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 20c0-4 3.6-6 8-6s8 2 8 6" />
        </svg>
        Settings
      </NavLink>
    </nav>
  )
}
