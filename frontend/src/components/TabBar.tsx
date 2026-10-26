import { NavLink } from 'react-router'

/** Bottom navigation. More tabs (Insights, Settings) arrive with later phases. */
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
    </nav>
  )
}
