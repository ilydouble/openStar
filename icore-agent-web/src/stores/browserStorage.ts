/**
 * Resolve the same persisted Storage instance for reads and writes.
 * Prefer window/localStorage explicitly so we never mix environments (e.g. wrong global binding).
 */
export function getBrowserStorage(): Storage | null {
  try {
    if (typeof globalThis === 'undefined') return null
    const scoped =
      typeof globalThis.window !== 'undefined' &&
      globalThis.window !== null &&
      globalThis.window.localStorage
        ? globalThis.window.localStorage
        : typeof globalThis.localStorage !== 'undefined'
          ? globalThis.localStorage
          : typeof localStorage !== 'undefined'
            ? localStorage
            : null
    if (!scoped || typeof scoped.getItem !== 'function') return null
    // Probe: restricted contexts throw on access rather than exposing null.
    void scoped.length
    return scoped
  } catch {
    return null
  }
}

/**
 * Read one string from browser storage with a fallback.
 */
export function readStoredString(
  storage: Storage | null | undefined,
  key: string,
  fallback = '',
): string {
  try {
    return storage?.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

/**
 * Persist one string value in browser storage.
 */
export function writeStoredString(
  storage: Storage | null | undefined,
  key: string,
  value: string,
): void {
  if (!storage) return
  try {
    storage.setItem(key, value)
  } catch {
    // Quota, private mode, or security restrictions — caller may use RAM fallback for this tab.
  }
}

/**
 * Remove one key from browser storage.
 */
export function removeStoredKey(storage: Storage | null | undefined, key: string): void {
  if (!storage) return
  storage.removeItem(key)
}
