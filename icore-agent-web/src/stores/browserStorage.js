/**
 * Resolve the same persisted Storage instance for reads and writes.
 * Prefer window/localStorage explicitly so we never mix environments (e.g. wrong global binding).
 * @returns {Storage | null}
 */
export function getBrowserStorage() {
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
 * @param {Storage | null | undefined} storage
 * @param {string} key
 * @param {string} fallback
 */
export function readStoredString(storage, key, fallback = '') {
  try {
    return storage?.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

/**
 * Persist one string value in browser storage.
 * @param {Storage | null | undefined} storage
 * @param {string} key
 * @param {string} value
 */
export function writeStoredString(storage, key, value) {
  if (!storage) return
  try {
    storage.setItem(key, value)
  } catch {
    // Quota, private mode, or security restrictions — caller may use RAM fallback for this tab.
  }
}

/**
 * Remove one key from browser storage.
 * @param {Storage | null | undefined} storage
 * @param {string} key
 */
export function removeStoredKey(storage, key) {
  if (!storage) return
  storage.removeItem(key)
}
