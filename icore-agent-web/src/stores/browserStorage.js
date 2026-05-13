/**
 * Resolve localStorage safely so modules remain importable in tests and SSR-like contexts.
 * @returns {Storage | null}
 */
export function getBrowserStorage() {
  return typeof localStorage === 'undefined' ? null : localStorage
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
  storage.setItem(key, value)
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
