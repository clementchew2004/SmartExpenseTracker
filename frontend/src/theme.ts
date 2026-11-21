/** Light / Dark / Match phone, remembered in this browser (your choice: per
 * device). Applied as <html data-theme="...">, which index.css reads. */
export type Theme = 'light' | 'dark' | 'system'

const KEY = 'theme'

export function savedTheme(): Theme {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system' // private mode or blocked storage: follow the phone
  }
}

export function applyTheme(theme: Theme) {
  if (theme === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
  try {
    if (theme === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme)
  } catch {
    // Not remembered this time; it still applies until the page reloads.
  }
}
