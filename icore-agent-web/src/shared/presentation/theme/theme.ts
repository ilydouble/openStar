/** Theme: Tailwind dark mode via `class="dark"` on <html>. */

import {
  getBrowserStorage,
  readStoredString,
  writeStoredString,
} from '../../infrastructure/storage/browserStorage'

export const THEME_STORAGE_KEY = 'icore-theme'

export type ThemeMode = 'light' | 'dark'

/** Initialize the document theme from persisted browser preference. */
export function initTheme(): void {
  const root = document.documentElement
  try {
    const saved = readStoredString(getBrowserStorage(), THEME_STORAGE_KEY, '')
    if (saved === 'light') root.classList.remove('dark')
    else root.classList.add('dark')
  } catch {
    root.classList.add('dark')
  }
}

/** Return whether the current document is using dark mode. */
export function isDark(): boolean {
  return document.documentElement.classList.contains('dark')
}

/** Apply and persist the selected theme mode. */
export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement
  const storage = getBrowserStorage()
  if (mode === 'light') {
    root.classList.remove('dark')
    writeStoredString(storage, THEME_STORAGE_KEY, 'light')
  } else {
    root.classList.add('dark')
    writeStoredString(storage, THEME_STORAGE_KEY, 'dark')
  }
  window.dispatchEvent(new CustomEvent('icore-theme-change'))
}

/** Toggle between light and dark theme modes. */
export function toggleTheme(): void {
  applyTheme(isDark() ? 'light' : 'dark')
}
