/** Theme: Tailwind dark mode via `class="dark"` on <html>. */

export const THEME_STORAGE_KEY = 'icore-theme'

export function initTheme() {
  const root = document.documentElement
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'light') root.classList.remove('dark')
    else root.classList.add('dark')
  } catch {
    root.classList.add('dark')
  }
}

export function isDark() {
  return document.documentElement.classList.contains('dark')
}

export function applyTheme(mode) {
  const root = document.documentElement
  if (mode === 'light') {
    root.classList.remove('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'light')
  } else {
    root.classList.add('dark')
    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
  }
  window.dispatchEvent(new CustomEvent('icore-theme-change'))
}

export function toggleTheme() {
  applyTheme(isDark() ? 'light' : 'dark')
}
